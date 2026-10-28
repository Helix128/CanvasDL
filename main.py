import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import urllib.parse
from playwright.sync_api import sync_playwright
import requests

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.instructure.com").rstrip("/")
SESSION_FILE = Path("session.json")
TOKEN_FILE = Path("canvas_token.txt")


def ensure_canvas_session():
    """Abre el navegador para iniciar sesión si no existe una sesión guardada."""
    if SESSION_FILE.exists():
        print(f"✓ Sesión encontrada en {SESSION_FILE}")
        return

    print("Iniciando navegador para iniciar sesión en Canvas...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(CANVAS_BASE_URL)

        print("Abriendo portal universitario de Canvas...")
        print("Inicia sesión con tu correo universitario (SSO)...")
        print("Tienes hasta 5 minutos para completar el inicio de sesión y 2FA.")

        # Espera a que cargue la interfaz principal de Canvas tras completar el login SSO
        try:
            page.wait_for_selector(
                "#global_nav_profile_link, .ic-app-header__main-navigation, #dashboard",
                timeout=300_000,
            )
        except Exception:
            # Fallback por URL si el tema visual de Canvas oculta los selectores estándar
            page.wait_for_url(
                lambda url: "instructure.com" in url and "login" not in url and "auth2" not in url,
                timeout=60_000,
            )

        # Pequeña pausa para asegurar que todas las cookies de sesión se hayan asentado
        page.wait_for_timeout(2000)

        # Guarda cookies y estado de almacenamiento en disco
        context.storage_state(path=SESSION_FILE)
        print(f"✓ Sesión guardada exitosamente en {SESSION_FILE}")

        browser.close()


def get_requests_session() -> requests.Session:
    """Crea una sesión de requests con las cookies extraídas de Playwright."""
    ensure_canvas_session()

    session = requests.Session()
    with open(SESSION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Inyectar las cookies de Playwright en la sesión de requests
    for cookie in data.get("cookies", []):
        if "instructure.com" in cookie.get("domain", ""):
            session.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

    return session


def create_canvas_api_token(
    session: requests.Session,
    purpose: str = "CanvasDL",
    expires_in_days: int = 89,
    expires_at: str | None = None,
) -> str:
    """Genera automáticamente un token de API de Canvas mediante el endpoint oficial de configuración."""
    csrf_raw = session.cookies.get("_csrf_token")
    if not csrf_raw:
        raise ValueError("No se encontró la cookie '_csrf_token' en la sesión.")

    csrf_token = urllib.parse.unquote(csrf_raw)

    if not expires_at:
        exp_dt = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        expires_at = exp_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    headers = {
        "Accept": "application/json+canvas-string-ids, application/json",
        "Content-Type": "application/json",
        "x-csrf-token": csrf_token,
        "x-requested-with": "XMLHttpRequest",
        "Origin": CANVAS_BASE_URL,
        "Referer": f"{CANVAS_BASE_URL}/profile/settings",
    }

    payload = {
        "token": {
            "purpose": purpose,
            "expires_at": expires_at,
        }
    }

    print(f"Generando token de API en Canvas (Propósito: '{purpose}', Expira en: {expires_in_days} días [{expires_at}])...")
    resp = session.post(
        f"{CANVAS_BASE_URL}/api/v1/users/self/tokens",
        json=payload,
        headers=headers,
    )

    if resp.status_code == 200:
        data = resp.json()
        token = data.get("visible_token")
        if not token:
            raise ValueError(f"Respuesta inesperada al crear token: {data}")

        TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
        print(f"✓ ¡Token de API generado exitosamente y guardado en {TOKEN_FILE}!")
        print(f"  Expira el: {data.get('expires_at')}")
        return token
    elif resp.status_code == 401:
        print("⚠ Sesión inválida o expirada. Eliminando sesión para reiniciar...")
        SESSION_FILE.unlink(missing_ok=True)
        raise RuntimeError("Sesión expirada al intentar crear token de API.")
    else:
        raise RuntimeError(f"Error {resp.status_code} al crear token: {resp.text}")


def get_valid_api_token(force_refresh: bool = False) -> str:
    """Obtiene el token de API guardado, o lo crea automáticamente si no existe o expiró."""
    if not force_refresh and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            # Verificar si el token sigue activo consultando el perfil del usuario
            resp = requests.get(
                f"{CANVAS_BASE_URL}/api/v1/users/self",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                user_info = resp.json()
                print(f"✓ Token de API válido activo para: {user_info.get('name')} (ID: {user_info.get('id')})")
                return token
            else:
                print("⚠ El token guardado ya no es válido. Regenerando...")
                TOKEN_FILE.unlink(missing_ok=True)

    # Si no hay token, expiró o se fuerza la renovación
    session = get_requests_session()
    return create_canvas_api_token(session, expires_in_days=89)


def list_canvas_tokens(session: requests.Session | None = None) -> list[dict]:
    """Obtiene la lista de tokens registrados en la página de configuración del perfil."""
    if session is None:
        session = get_requests_session()

    resp = session.get(f"{CANVAS_BASE_URL}/profile/settings")
    if resp.status_code != 200:
        raise RuntimeError(f"Error {resp.status_code} al consultar configuración de usuario: {resp.text}")

    # Extraer tokens a partir de los enlaces de eliminación en el HTML
    tokens = []
    pattern = r"aria-label=\"Eliminar token ([^\"]+)\"[^>]*rel=\"([^\"]+)\""
    for match in re.finditer(pattern, resp.text):
        name = match.group(1).strip()
        endpoint = match.group(2).strip()
        token_id = endpoint.split("/")[-1]
        tokens.append({
            "name": name,
            "id": token_id,
            "delete_url": endpoint,
        })
    return tokens


def delete_canvas_token(token_id_or_url: str, session: requests.Session | None = None) -> bool:
    """Elimina / revoca un token de acceso de Canvas por su ID, clave o URL completa."""
    if session is None:
        session = get_requests_session()

    csrf_raw = session.cookies.get("_csrf_token")
    if not csrf_raw:
        raise ValueError("No se encontró la cookie '_csrf_token' en la sesión.")

    csrf_token = urllib.parse.unquote(csrf_raw)

    delete_url = (
        token_id_or_url
        if token_id_or_url.startswith("http")
        else f"{CANVAS_BASE_URL}/api/v1/users/self/tokens/{token_id_or_url}"
    )

    headers = {
        "Accept": "application/json, text/javascript, application/json+canvas-string-ids, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Origin": CANVAS_BASE_URL,
        "Referer": f"{CANVAS_BASE_URL}/profile/settings",
    }

    data = {
        "authenticity_token": csrf_token,
        "_method": "DELETE",
    }

    resp = session.post(delete_url, headers=headers, data=data)

    if resp.status_code == 200:
        print(f"✓ Token ({delete_url.split('/')[-1]}) eliminado correctamente.")
        return True
    else:
        print(f"⚠ Error {resp.status_code} al eliminar token: {resp.text}")
        return False


def revoke_saved_token() -> bool:
    """Revoca en Canvas el token que está guardado actualmente en disco y borra el archivo local."""
    if not TOKEN_FILE.exists():
        print("No hay token guardado localmente.")
        return False

    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    # Los tokens en Canvas suelen iniciar con un identificador numérico seguido de tilde
    token_prefix = token.split("~")[0] if "~" in token else token[:10]

    session = get_requests_session()
    tokens = list_canvas_tokens(session)

    target_token = None
    for t in tokens:
        if t["id"].startswith(token_prefix) or token_prefix.startswith(t["id"]):
            target_token = t
            break

    if target_token:
        print(f"Revocando token en Canvas ({target_token['name']}, ID: {target_token['id']})...")
        ok = delete_canvas_token(target_token["delete_url"], session)
        if ok:
            TOKEN_FILE.unlink(missing_ok=True)
            print(f"✓ Archivo {TOKEN_FILE} eliminado localmente.")
            return True
        return False
    else:
        print("No se encontró el token en Canvas (puede que ya haya sido eliminado).")
        TOKEN_FILE.unlink(missing_ok=True)
        return True


if __name__ == "__main__":
    import argparse
    import sys
    import threading
    import webbrowser
    import uvicorn

    parser = argparse.ArgumentParser(description="CanvasDL — Mission Control & Bulk Downloader")
    parser.add_argument("--cli", action="store_true", help="Solo verificar token sin abrir la interfaz gráfica")
    parser.add_argument("--port", type=int, default=8000, help="Puerto para el servidor web local (defecto: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()

    print("=" * 60)
    print("           CanvasDL — Mission Control & Bulk Downloader")
    print("=" * 60)
    token = get_valid_api_token()

    if args.cli:
        print("\nToken listo para usar:")
        print(token)
        sys.exit(0)

    url = f"http://127.0.0.1:{args.port}"
    print(f"\n🚀 Iniciando interfaz web en: {url}")
    print("Presiona Ctrl+C en esta terminal para detener la aplicación.\n")

    if not args.no_browser:
        def _open():
            import time
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("app.server:app", host="127.0.0.1", port=args.port, log_level="info")
