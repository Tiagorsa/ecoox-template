import os
from typing import Optional, Any, Dict, List
from fastapi import FastAPI, HTTPException, Header, Path
from pydantic import BaseModel, Field, validator
import httpx

# =========================================================
# Configurações FIXAS / ENV
# =========================================================
EFIX_BASE_HOST = os.getenv("EFIX_BASE_HOST", "api4.ecosim.com.br")
TIMEOUT_SECS = float(os.getenv("EFIX_HTTP_TIMEOUT", "15"))

def base_url() -> str:
    host = EFIX_BASE_HOST.strip()
    if host.startswith("http://"):
        host = host[7:]
    if host.startswith("https://"):
        host = host[8:]
    return f"https://{host}"

# =========================================================
# Modelos
# =========================================================
class ContactCreate(BaseModel):
    # name é opcional aqui; se não vier, usaremos number como nome no createContact
    name: Optional[str] = Field(None, description="Nome do contato; se ausente usa o número")
    number: str = Field(..., description="E.164, ex: 5515998566622")
    email: Optional[str] = None
    cpf: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    businessName: Optional[str] = None
    birthdayDate: Optional[str] = Field(None, description="ex: 01/01/1990")
    externalKey: Optional[str] = None

    @validator("number")
    def clean_number(cls, v): return v.strip()

class TemplateLanguage(BaseModel):
    code: str = Field(..., example="en_US")

class TemplateObject(BaseModel):
    name: str = Field(..., example="hello_world")
    language: TemplateLanguage
    components: Optional[List[Dict[str, Any]]] = None  # compat Cloud API

class TemplateData(BaseModel):
    messaging_product: str = Field("whatsapp", const=True)
    to: str
    type: str = Field("template", const=True)
    template: TemplateObject

class SendTemplateBody(BaseModel):
    # payload mínimo
    number: str = Field(..., description="Destino E.164")
    isClosed: Optional[bool] = False

    # escolha A: deixe a lib montar com name+language
    template_name: Optional[str] = Field(None, example="hello_world")
    template_language_code: Optional[str] = Field(None, example="en_US")

    # escolha B: envie o bloco templateData pronto
    templateData: Optional[TemplateData] = None

    # dados de contato (usados se showcontact == 404)
    contact: Optional[ContactCreate] = None

    @validator("number")
    def clean_number(cls, v): return v.strip()

    @validator("templateData", always=True)
    def ensure_template(cls, v, values):
        if v is not None:
            return v
        name = values.get("template_name")
        code = values.get("template_language_code")
        number = values.get("number")
        if name and code and number:
            return TemplateData(
                messaging_product="whatsapp",
                to=number,
                type="template",
                template=TemplateObject(
                    name=name,
                    language=TemplateLanguage(code=code),
                ),
            )
        raise ValueError(
            "Envie templateData completo OU (template_name + template_language_code)."
        )

# =========================================================
# Auxiliares HTTP
# =========================================================
async def post_json(url: str, data: Dict[str, Any], bearer: Optional[str]) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECS) as client:
        return await client.post(url, json=data, headers=headers)

def safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:1000]}

def extract_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)  # split once
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    # se vier só o token (sem o prefixo), aceitamos mesmo assim
    return auth_header.strip()

# =========================================================
# FastAPI
# =========================================================
app = FastAPI(
    title="Template Sender and create contact",
    version="1.1.0",
    description="Verifica contato, cria se necessário e envia template. Encaminha Authorization Bearer para os endpoints externos."
)

@app.get("/health")
async def health():
    return {"ok": True, "base_url": base_url()}

# ---------------------------
# NOVO ENDPOINT:
# POST /v2/api/external/{canal_token}/template
# ---------------------------
@app.post("/v2/api/external/{canal_token}/template")
async def template_endpoint(
    payload: SendTemplateBody,
    canal_token: str = Path(..., description="Token do canal para show/create"),
    Authorization: Optional[str] = Header(None, convert_underscores=False),
):
    """
    Recebe Authorization: Bearer <TEMPLATE_TOKEN> e repassa para:
    - {BASE_URL}/v2/api/external/{canal_token}/showcontact
    - {BASE_URL}/v2/api/external/{canal_token}/createContact
    - {BASE_URL}/v2/api/external/{TEMPLATE_TOKEN}/template
    """
    template_token = extract_bearer(Authorization)
    if not template_token:
        raise HTTPException(status_code=401, detail="Authorization Bearer requerido")

    BASE_URL = base_url()

    # URLs externas corretas (sem o bug de 'emplate')
    url_show = f"{BASE_URL}/v2/api/external/{canal_token}/showcontact"
    url_create = f"{BASE_URL}/v2/api/external/{canal_token}/createContact"
    url_template = f"{BASE_URL}/v2/api/external/{template_token}/template"

    steps: List[Dict[str, Any]] = []

    # 1) showcontact
    try:
        r_show = await post_json(url_show, {"number": payload.number}, template_token)
        steps.append({"step": "showcontact", "status_code": r_show.status_code, "url": url_show, "response": safe_json(r_show)})
        if r_show.status_code == 404:
            # 2) createContact exigirá dados; se name ausente, usa o number
            if not payload.contact:
                raise HTTPException(
                    status_code=400,
                    detail="Número não encontrado e 'contact' não foi fornecido para criação."
                )
            contact_data = payload.contact.dict()
            if not contact_data.get("name"):
                contact_data["name"] = payload.number  # regra solicitada
            # garantir que number do contact exista e seja o mesmo number
            contact_data["number"] = payload.number

            r_create = await post_json(url_create, contact_data, template_token)
            steps.append({"step": "createContact", "status_code": r_create.status_code, "url": url_create, "response": safe_json(r_create)})
            if r_create.status_code not in (200, 201):
                raise HTTPException(
                    status_code=502,
                    detail={"msg": "Falha ao criar contato", "response": safe_json(r_create)}
                )
        elif r_show.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail={"msg": "Falha na verificação do contato", "response": safe_json(r_show)}
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erro de rede em showcontact/create: {e!s}")

    # 3) enviar template
    payload_template = {
        "number": payload.number,
        "isClosed": bool(payload.isClosed),
        "templateData": payload.templateData.dict()
    }
    try:
        r_template = await post_json(url_template, payload_template, template_token)
        steps.append({"step": "template", "status_code": r_template.status_code, "url": url_template, "response": safe_json(r_template)})
        if r_template.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail={"msg": "Falha ao enviar template", "response": safe_json(r_template)}
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Erro de rede ao enviar template: {e!s}")

    return {"ok": True, "message": "Template enviado (contato verificado/criado).", "steps": steps}
