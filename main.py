from fastapi import FastAPI, HTTPException, Header, Path
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import httpx
import os
from datetime import datetime

# =========================
# Configurações Fixas
# =========================
BASE_URL = os.getenv("BASE_URL", "https://chatapi.efixtelecom.com.br")
TIMEOUT_SECS = float(os.getenv("HTTP_TIMEOUT", "15"))

# =========================
# Modelos
# =========================
class TemplateLanguage(BaseModel):
    code: str = "en_US"

class TemplateObject(BaseModel):
    name: str = "hello_world"
    language: TemplateLanguage

class TemplateData(BaseModel):
    messaging_product: str = "whatsapp"
    to: str
    type: str = "template"
    template: TemplateObject

class Contact(BaseModel):
    number: str
    name: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    businessName: Optional[str] = None
    birthdayDate: Optional[str] = None
    externalKey: Optional[str] = None

class TemplateRequest(BaseModel):
    number: str = Field(..., description="Número destino no formato E.164")
    isClosed: Optional[bool] = False
    templateData: TemplateData
    contact: Optional[Contact] = None

# =========================
# Funções Auxiliares
# =========================
async def post_json(url: str, data: Dict[str, Any], token: str) -> httpx.Response:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
        return await client.post(url, json=data, headers=headers)

def safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:1000]}

# =========================
# FastAPI App
# =========================
app = FastAPI(
    title="Template Sender and create contact",
    version="1.0.1",
    description="Verifica contato, cria se necessário e envia template via API externa."
)

# =========================
# Endpoint de teste GET /
# =========================
@app.get("/")
async def get_server_time():
    """Retorna data/hora atual do servidor"""
    return {
        "server_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "America/Sao_Paulo"
    }

# =========================
# Endpoint principal
# =========================
@app.post("/v2/api/external/{canal_token}/template")
async def send_template(
    canal_token: str = Path(..., description="Token do canal externo"),
    request: TemplateRequest = None,
    authorization: str = Header(..., description="Authorization: Bearer <API Key>"),
):
    # Extrai token de autorização
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Cabeçalho Authorization inválido")
    token = authorization.split(" ", 1)[1].strip()

    # URLs externas
    url_show = f"{BASE_URL}/v2/api/external/{canal_token}/showcontact"
    url_create = f"{BASE_URL}/v2/api/external/{canal_token}/createContact"
    url_template = f"{BASE_URL}/v2/api/external/{canal_token}/template"

    steps = []

    # 1️⃣ Verifica se o número existe
    try:
        r_show = await post_json(url_show, {"number": request.number}, token)
        steps.append({"step": "showcontact", "status": r_show.status_code})
        if r_show.status_code == 404:
            # 2️⃣ Cria contato se não existir
            contact = request.contact or Contact(number=request.number)
            if not contact.name:
                contact.name = contact.number
            r_create = await post_json(url_create, contact.dict(), token)
            steps.append({"step": "createContact", "status": r_create.status_code, "response": safe_json(r_create)})
            if r_create.status_code not in (200, 201):
                raise HTTPException(status_code=502, detail="Falha ao criar contato")
        elif r_show.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="Erro na verificação do contato")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erro de rede: {e!s}")

    # 3️⃣ Envia o template
    payload = {
        "number": request.number,
        "isClosed": request.isClosed,
        "templateData": request.templateData.dict(),
    }
    try:
        r_template = await post_json(url_template, payload, token)
        steps.append({"step": "template", "status": r_template.status_code, "response": safe_json(r_template)})
        if r_template.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="Falha ao enviar template")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erro ao enviar template: {e!s}")

    return {"ok": True, "steps": steps}
