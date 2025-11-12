# Template Sender and create contact (FastAPI)

Serviço que:
1) Verifica contato via **showcontact**  
2) Cria contato via **createContact** (se 404)  
3) Envia **template**  

Todos os POSTs externos recebem **Authorization: Bearer <TOKEN>** vindo **do mesmo header** da chamada ao nosso endpoint.

```markdown
# Template Sender and create contact (FastAPI)

Serviço que:
1) Verifica contato via **showcontact**  
2) Cria contato via **createContact** (se 404)  
3) Envia **template**  

Todos os POSTs externos recebem **Authorization: Bearer <TOKEN>** vindo **do mesmo header** da chamada ao nosso endpoint.

## Endpoint

```

POST /v2/api/external/{canal_token}/template
Authorization: Bearer <TEMPLATE_TOKEN>
Content-Type: application/json

````

### Body (modos)

**A. Deixe o serviço montar o template mínimo**
```json
{
  "number": "5515998566622",
  "isClosed": false,
  "template_name": "hello_world",
  "template_language_code": "en_US",
  "contact": {
    "name": "Nome (opcional)",
    "number": "5515998566622",
    "email": "contato@email.com",
    "cpf": "012.345.678.91",
    "firstName": "Nome Principal",
    "lastName": "Sobrenome",
    "businessName": "Empresa",
    "birthdayDate": "01/01/1990",
    "externalKey": "fix-value"
  }
}
````

> Se `contact.name` não for enviado, o serviço usa o **número** como `name` no `createContact`.

**B. Envie `templateData` completo**

```json
{
  "number": "5515998566622",
  "isClosed": false,
  "templateData": {
    "messaging_product": "whatsapp",
    "to": "5515998566622",
    "type": "template",
    "template": {
      "name": "hello_world",
      "language": { "code": "en_US" }
    }
  }
}
```

## Variáveis de Ambiente

* `EFIX_BASE_HOST` (default: `api4.ecosim.com.br`)
* `EFIX_HTTP_TIMEOUT` (default: `15`)

## Executar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Exemplos de cURL

```bash
# usando TEMPLATE_TOKEN no Authorization e canal_token na URL
curl -s -X POST "http://localhost:8000/v2/api/external/7e862d5e-87a3-4e3c-80e7-6c26301f11d7/template" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer EYJ..." \
  -d '{
    "number": "5515998566622",
    "isClosed": false,
    "template_name": "hello_world",
    "template_language_code": "en_US"
  }'
```

## Deploy no EasyPanel

1. **Create App → Dockerfile**
2. **Build Context**: repositório com `Dockerfile` e estes arquivos
3. **Porta interna**: `8000`
4. **Env Vars**:

   * `EFIX_BASE_HOST=api4.ecosim.com.br`
   * `EFIX_HTTP_TIMEOUT=15`
5. **Domínio/HTTPS**: configure o domínio e ative SSL (o EasyPanel usa Traefik + Certbot)

```
