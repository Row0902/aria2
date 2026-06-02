# CODE-REVIEW-RULES.md — aria2 Python SDK

> Reglas de revisión para el SDK aria2. Todo PR debe cumplir estos estándares antes de mergear.
> Incumplen lint → request changes. Incumplen arquitectura → bloquean el PR.

---

## 1. Tamaño de Archivos

```
Standard:   ≤ 200 líneas por archivo
Límite duro: ≤ 500 líneas por archivo — NO SE NEGOCIA
```

### Cómo cumplirlo

- Un archivo que supera 200 líneas **debe** dividirse tan pronto como se identifique.
- 500 líneas es límite de CI/CD — el workflow falla si se excede.
- La división sigue criterios de responsabilidad única (ver regla 5).

### Ejemplo

```python
# ❌ Mal: 401 líneas, mezcla transporte, lógica de negocio y parsing
src/aria2/client/__init__.py

# ✅ Bien: transport/http.py = HTTP transport, transport/ws.py = WS transport
src/aria2/client/transport/http.py   # 75 lines
src/aria2/client/transport/ws.py     # 171 lines
```

---

## 2. Programación Orientada a Objetos Estricta

```
Toda la lógica de dominio VIVE dentro de clases.
NO se permiten módulos con solo funciones sueltas.
```

### Reglas

- **Prohibido**: módulos `__init__.py` con lógica procedural sin clases.
- **Prohibido**: funciones `_helper()` globales fuera de una clase — van como `@staticmethod` o `@classmethod`.
- **Permitido**: `utils.py` con utilidades PURAS (sin estado, sin side effects) solo si hay 3+ usos.
- **Exigido**: abstract base classes (ABC) para interfaces de transporte, parsers, y policies.

### Ejemplo

```python
# ✅ Bien: clase con responsabilidad definida
class HttpTransport(Transport):
    """JSON-RPC over HTTP via httpx."""

    async def connect(self) -> None:
        ...

# ❌ Mal: funciones sueltas en módulo
def send_http_request(host, port, body):
    ...
def parse_http_response(data):
    ...
```

---

## 3. Validación Polimórfica Estricta

```
Donde hay variantes de un tipo, DEBE usarse discriminated unions
con Pydantic o TypeAdapter. No if/elif/else manual.
```

### Reglas

- **Prohibido**: cadenas de `if/elif/else` para distinguir variantes de un tipo.
- **Exigido**: `Discriminator` + `Annotated[Union[...], Discriminator(...)]` para tipos variables.
- **Exigido**: `TypeAdapter` para parsear colecciones o uniones en una línea.
- **Permitido**: `match/case` SOLO si el pattern matching cubre todos los casos (exhaustivo).

### Ejemplo

```python
# ✅ Bien: discriminated union con Pydantic
def _status_discriminator(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("status", "active")
    if hasattr(v, "status"):
        return v.status
    return "active"

DownloadStatusResult = Annotated[
    Union[ActiveStatus, PausedStatus, ErrorStatus, CompleteStatus, RemovedStatus],
    Discriminator(_status_discriminator),
]

# ❌ Mal: if/elif/else manual para determinar tipo
def parse_status(data):
    if data["status"] == "active":
        return ActiveStatus(**data)
    elif data["status"] == "paused":
        return PausedStatus(**data)
    ...
```

---

## 4. Un Archivo, Una Clase

```
Cada archivo .py contiene EXACTAMENTE UNA clase pública.
```

### Excepciones

- Clases privadas (`_` prefijo) que son soporte exclusivo de la clase pública del archivo.
- Clases excepcionalmente pequeñas (error types, value objects) pueden agruparse SOLO si suman ≤ 30 líneas.
- ABC (interfaces) van en su propio archivo: `transport/__init__.py` para `Transport`.

### Ejemplo

```python
# ✅ Bien: un archivo = una clase
src/aria2/client/transport/http.py          # HttpTransport
src/aria2/client/transport/ws.py            # WebSocketTransport
src/aria2/errors/__init__.py                # Excepciones agrupadas (< 30 lines)
src/aria2/types/__init__.py                 # Enums agrupados (< 30 lines)

# ❌ Mal: múltiples clases públicas en un archivo
src/aria2/models/__init__.py                # 11 clases públicas
```

---

## 5. Métodos Públicos por Clase: ≤ 10

```
Ninguna clase pública expone más de 10 métodos públicos.
```

### Cómputo

Cuentan como métodos públicos:
- `def metodo` sin prefijo `_`
- `@property` y `@xxx.setter`
- `async def metodo`

NO cuentan:
- Dunders (`__init__`, `__aenter__`, `__aexit__`, `__str__`)
- Métodos privados/protegidos (`_metodo`, `__metodo`)
- `@staticmethod` y `@classmethod` (si son utilidad interna)

### Estrategia de división

Cuando una clase excede 10 métodos públicos:

```
# ❌ Mal: Aria2Client con 30+ métodos públicos
class Aria2Client:
    def add_uri(self): ...
    def add_torrent(self): ...
    def add_metalink(self): ...
    def remove(self): ...
    def pause(self): ...
    # ... 25 métodos más

# ✅ Bien: separado por sub-dominios
class Aria2Client:
    # Lifecycle (4)
    async def connect(self): ...
    async def close(self): ...
    async def __aenter__(self): ...
    async def __aexit__(self): ...

    # Delega a objetos especializados
    @property
    def downloads(self) -> DownloadManager: ...
    @property
    def system(self) -> SystemManager: ...
    @property
    def events(self) -> EventManager: ...

class DownloadManager:
    def add_uri(self): ...
    def add_torrent(self): ...
    def remove(self): ...
    def pause(self): ...
    def tell_status(self): ...
    # ≤ 10 métodos públicos

class SystemManager:
    def get_version(self): ...
    def get_session_info(self): ...
    def shutdown(self): ...
    # ≤ 10 métodos públicos
```

---

## 6. Funciones < 20 Líneas, Responsabilidad Única

```
Toda función/método tiene ≤ 20 líneas de cuerpo (sin contar firma, docstring, blanks).
Toda función/método hace EXACTAMENTE UNA COSA.
```

### Cómo medir

```python
def send_request(self, method: str, params: list[Any]) -> Any:
    """Send JSON-RPC request and return parsed result."""  # ← no cuenta
                                                             # ← blank no cuenta
    body = _build(method, params, secret=self._secret)       # 1
    try:                                                      # 2
        resp = await self._client.post(self._url(), json=body)  # 3
        resp.raise_for_status()                               # 4
        data = resp.json()                                    # 5
    except httpx.HTTPError as e:                              # 6
        raise Aria2ConnectionError(str(e)) from e             # 7
                                                              # ← blank no cuenta
    return _parse(data)                                       # 8
# Total: 8 líneas ✅
```

### Señales de que una función hace más de una cosa

- Tiene `and`/`or` en el nombre: `validate_and_save()`
- Tiene comentarios `# Step 1`, `# Step 2` dentro del cuerpo
- Tiene más de 2 niveles de indentación (`if` dentro de `for` dentro de `try`)
- Modifica argumentos Y retorna un valor
- Mezcla lógica de negocio con I/O

### Ejemplo

```python
# ❌ Mal: 3 responsabilidades, 45 líneas
async def add_download(self, uri, options):
    # 1. Validar URI
    if not uri.startswith(("http", "https", "magnet", "ftp")):
        raise ValueError("Invalid URI")
    # 2. Construir request
    params = [uri]
    if options:
        params.append(options)
    # 3. Enviar RPC + parsear
    body = _build("aria2.addUri", params, secret=self._secret)
    resp = await self._client.post(self._url(), json=body)
    data = resp.json()
    if "error" in data:
        raise Aria2RpcError(data["error"]["code"], data["error"]["message"])
    return data["result"]

# ✅ Bien: cada responsabilidad en su capa
def _validate_uri(uri: str) -> None:
    """Validate download URI format."""
    if not uri.startswith(("http://", "https://", "magnet:", "ftp://")):
        raise ValueError(f"Invalid URI scheme: {uri}")

async def add_uri(self, uris: list[str], options: dict | None = None) -> GID:
    """Add a download by URI."""
    for uri in uris:
        _validate_uri(uri)
    params: list[Any] = [uris]
    if options:
        params.append(options)
    return await self._request("aria2.addUri", params)
```

---

## 7. Nomenclatura y Estilo

| Elemento | Convención | Ejemplo |
|---|---|---|
| Clases | PascalCase | `Aria2Client`, `HttpTransport` |
| Métodos/funciones | snake_case | `add_uri()`, `tell_status()` |
| Variables | snake_case | `download_speed`, `total_length` |
| Constantes | UPPER_SNAKE | `JSON_RPC_VERSION`, `DEFAULT_TIMEOUT` |
| Privado | `_` prefijo | `_request()`, `_connected` |
| Muy privado | `__` prefijo (name mangling) | `__internal_state` |
| Tipos | PascalCase | `GID`, `DownloadStatus` |
| Archivos | snake_case | `http.py`, `ws.py` |

---

## 8. Tipado Estricto

```
Toda función/método tiene anotaciones de tipo COMPLETAS.
Any es la excepción, no la regla.
ty check pasa con --error-on-warning.
```

### Reglas

- **Obligatorio**: toda función/método tiene tipo de retorno explícito (` → T`).
- **Obligatorio**: todo parámetro tiene tipo explícito.
- **Obligatorio**: toda propiedad pública tiene tipo de retorno.
- **Obligatorio**: `ty check src/ --error-on-warning` pasa en CI.
- **Prohibido**: `Any` como tipo de parámetro o retorno sin comentario `# Any: <razón>`.
- **Prohibido**: `dict` sin parámetros de tipo — usar `dict[str, Any]` si no hay más específico.
- **Prohibido**: `list` sin parámetros de tipo — usar `list[str]`.
- **Prohibido**: `Optional[X]` — usar `X | None` (Python 3.14).
- **Prohibido**: `Union[X, Y]` — usar `X | Y`.
- **Prohibido**: `# type: ignore` legacy — usar `# ty: ignore = <rule>`.
- **Prohibido**: `# ty: ignore` sin comentario explicativo de por qué es necesario.
- **Prohibido**: `cast(T, x)` sin comentario de por qué el type checker no infiere el tipo.
- **Exigido**: Type narrowing con `isinstance()`, `TypeGuard`, `TypeIs`, o `match/case`.
- **Opcional**: `from __future__ import annotations` **ya no es necesario** (PEP 649/749 en 3.14). Se permite para compatibilidad con type checkers legacy pero no se exige.

### Prioridad de tipos

```
1. Tipos específicos:  list[str] | dict[str, int] | GID | DownloadStatus
2. Tipos genéricos:    Sequence[str]  (cuando aceptas tuple y list)
3. Protocols:          Callable[[int], str] | Protocol con métodos
4. Any:                ⚠️ SOLO como último recurso, con comentario
```

### Ejemplo

```python
# ✅ Bien: tipado completo y específico
from __future__ import annotations
from typing import Any

class HttpTransport(Transport):
    async def send_request(self, method: str, params: list[Any]) -> Any:
        """Send a JSON-RPC request and return the result."""  # Any: respuesta dinámica del daemon
        body = _build(method, params, secret=self._secret)
        resp = await self._client.post(self._url(), json=body)
        return _parse(resp.json())

# ❌ Mal: tipos omisos, Any sin excusa, type: ignore legacy
def parse(data):              # ❌ falta tipo retorno
    ...
def send(method, params):     # ❌ faltan tipos parámetros
    ...
x = foo()  # type: ignore    # ❌ legacy comment
```

---

## 9. Namespace Estricto

```
Cada paquete declara su API pública explícitamente en __all__.
No hay fugas de import. No hay import circulares.
```

### Reglas

- **Obligatorio**: `__all__` explícito en **todo** `__init__.py`.
- **Obligatorio**: `__all__` contiene solo lo que es público (clases, funciones, tipos).
- **Obligatorio**: sub-módulos privados usan prefijo `_` en el nombre del archivo: `_helpers.py`.
- **Prohibido**: `from modulo import *` en código fuente — solo permitido en `__init__.py` CON `__all__` definido.
- **Prohibido**: importaciones circulares entre módulos del mismo paquete.
- **Prohibido**: módulos `__init__.py` con lógica de negocio — solo re-exportan.
- **Prohibido**: exponer tipos o funciones importadas de terceros sin alias o re-export explícita.
- **Exigido**: `__all__` ordenado alfabéticamente.
- **Exigido**: prefijo `_` en todo símbolo que no sea parte de la API pública del módulo.
- **Exigido**: los tests importan desde el paquete (`from aria2 import Aria2Client`), no desde archivos internos (`from aria2.client import Aria2Client`).

### Ejemplo

```python
# ✅ Bien: __init__.py con __all__ explícito y solo re-exports
"""Aria2 SDK — async JSON-RPC client for aria2."""

from __future__ import annotations

from aria2.client import Aria2Client
from aria2.errors import (
    Aria2AuthError,
    Aria2BinaryNotFoundError,
    Aria2ConnectionError,
    Aria2Error,
    Aria2RpcError,
)
from aria2.types import GID, DownloadStatus, PositionHow

__all__ = [
    "Aria2AuthError",
    "Aria2BinaryNotFoundError",
    "Aria2Client",
    "Aria2ConnectionError",
    "Aria2Error",
    "Aria2RpcError",
    "DownloadStatus",
    "GID",
    "PositionHow",
]

# ✅ Bien: módulo privado con prefijo _
src/aria2/client/transport/_helpers.py   # 👈 privado

# ❌ Mal: __init__.py sin __all__
from .client import Aria2Client
from .errors import Aria2Error  # ❌ qué más hay? se filtra todo

# ❌ Mal: import circular
# src/aria2/client.py importa de src/aria2/models.py
# src/aria2/models.py importa de src/aria2/client.py  → 💥
```

### Estructura de imports permitida

```python
# ✅ Permitido
from aria2 import Aria2Client                                    # import público
from aria2.client.transport.http import HttpTransport            # import interno
from collections.abc import Callable                             # stdlib
from typing import Any                                           # typing

# ❌ Prohibido
from aria2.client.transport.http import *                        # star import sin __all__
import aria2.client.transport.http as http_mod                   # acceso indirecto al módulo
```

---

## 10. Python 3.14 Estricto

```
El proyecto corre sobre Python 3.14. Se usan sus features, no se evitan.
Prohibido escribir código como si fuera 3.12.
```

### PEP 649/749 — Anotaciones Diferidas (ACTIVAS POR DEFECTO)

Python 3.14 **no evalúa anotaciones al definir la función**. La evaluación es diferida hasta que se accede a `__annotations__` o `annotationlib.get_annotations()`.

```python
# ✅ Ya no se necesita from __future__ import annotations
#    Las anotaciones son diferidas por defecto

def procesar(items: list[MiTipo]) -> dict[str, Resultado]:
    # PEP 649 permite forward references sin strings
    pass

# ✅ Para introspectar anotaciones, usar annotationlib
from annotationlib import get_annotations, Format

anotaciones = get_annotations(func, format=Format.STRING)
# Format.VALUE — evalúa (puede fallar si hay undefined)
# Format.FORWARDREF — undefined → ForwardRef objects
# Format.STRING — cadenas fuente
```

**Reglas PEP 649:**
- ❌ No se exige `from __future__ import annotations` (innecesario en 3.14)
- ✅ Forward references directas: `def f(x: MiClase)` sin quotes
- ⚠️ Si modificás `__annotations__` directamente, los cambios NO se reflejan en `annotationlib.get_annotations()`. Usar `__annotate__` en su lugar.

### PEP 758 — `except` sin paréntesis

```python
# ✅ Válido en 3.14
except ValueError:
    pass

# ✅ Válido en 3.14 (grupo de excepciones)
except ValueError, TypeError:
    pass

# ❌ PEP 654 — exception groups requieren except*
except* ValueError as e:
    pass
```

### PEP 765 — `finally` sin control de flujo

**BREAKING CHANGE**: `return`, `break`, `continue` dentro de `finally` ahora son `SyntaxError`.

```python
# ❌ SyntaxError en 3.14
for x in items:
    try:
        procesar(x)
    except:
        log_error()
    finally:
        break  # 💥 SyntaxError: cannot break in finally

# ✅ Correcto: flag + break fuera
done = False
for x in items:
    try:
        procesar(x)
    except:
        log_error()
    else:
        done = True
    if done:
        break
```

### Tipado Moderno (Python 3.14)

| Feature | Uso | Ejemplo |
|---|---|---|
| `type` | Type alias sin `TypeAlias` | `type JSON = dict[str, Any]` |
| `override` | Decorador | `from typing import override` |
| `Never` | Función que nunca retorna | `def abort() -> Never: ...` |
| `Self` | Return type de la misma clase | `from typing import Self` |
| `TypeVar` con defaults | Genéricos con default | `T = TypeVar("T", default=str)` |
| `Unpack` | Variadic generics | `from typing import Unpack` |
| `LiteralString` | String literal | `from typing import LiteralString` |

### asyncio 3.14 para Debugging

```bash
# Inspeccionar tareas asyncio de un proceso en ejecución
python -m asyncio ps <PID>       # Listar tareas
python -m asyncio pstree <PID>   # Árbol de corrutinas
```

Útil para debuggear conexiones colgadas, reader loops bloqueados, o timeouts.

### Reglas

- **Exigido**: todo código aprovecha Python 3.14 (`| None`, `| Union`, `match/case`, `except X, Y:`).
- **Prohibido**: `return/break/continue` en bloques `finally`.
- **Prohibido**: escribir código compatible con Python < 3.14.
- **Exigido**: `asyncio.timeout()` en vez de `asyncio.wait_for()`.
- **Exigido**: `TaskGroup` para tareas concurrentes relacionadas.
- **Recomendado**: `type alias = ...` en vez de `TypeAlias`.
- **Recomendado**: `annotationlib.get_annotations()` en vez de acceder a `__annotations__` directo.

---

## 11. Archivos de Tests

```
Un archivo de test por archivo fuente.
tests/test_<modulo>.py  →  src/<modulo>.py
```

### Reglas

- Tests siguen la misma estructura de paquetes que `src/`.
- Tests unitarios: sin I/O de red. Usar `AsyncMock`, `MagicMock`, `respx`.
- Tests de integración: marcados `@pytest.mark.integration`.
- Nombrar fixtures descriptivamente: `connected_client`, `mock_rpc`, `ws_server_state`.

---

## 12. Lo que NO se acepta en PR

- ❌ Archivos > 500 líneas (CI bloquea)
- ❌ Clases con > 10 métodos públicos
- ❌ Funciones > 20 líneas (a menos que el reviewer lo apruebe explícitamente con comentario)
- ❌ Cadenas `if/elif/else` para polimorfismo manual
- ❌ Excepciones de terceros sin wrappear (`httpx`, `websockets`, `json`)
- ❌ `except Exception` sin re-raise o manejo específico
- ❌ `# type: ignore` o `# ty: ignore` sin comentario explicativo
- ❌ `Any` sin comentario justificando su uso
- ❌ `__all__` faltante en `__init__.py`
- ❌ Secrets/tokens logueados sin mask
- ❌ Código sin test (excepto refactors triviales)
- ❌ Múltiples clases públicas en un archivo
- ❌ `asyncio.CancelledError` silenciado (`except Exception` lo captura en Python 3.14)
- ❌ Imports circulares
- ❌ `return/break/continue` dentro de `finally` (PEP 765)

---

## 13. Checklist de Revisión (orden)

1. **API pública**: firmas, tipos, `__all__`, nombres consistentes
2. **Tipado**: `ty check --error-on-warning`, sin `Any` sin excusa
3. **Python 3.14**: PEP 649/749/758/765, asyncio, typing moderno
4. **Namespaces**: `__all__` completo, sin leaks, sin circulares
5. **Tamaños**: archivo ≤ 200/500, función ≤ 20, métodos ≤ 10
6. **OOP**: clases, no funciones sueltas
7. **Polimorfismo**: discriminated unions, no if/elif
8. **Errores**: 3rd-party wrappeado, jerarquía `Aria2Error`
9. **Async**: cancelación, timeouts, lifecycle
10. **Tests**: cobertura de casos borde
11. **Documentación**: docstrings Google-style, CHANGELOG
12. **CI**: lint, type-check, test pasan
13. **Commits**: conventional commit, mensaje claro

---

*Documento de reglas del proyecto aria2 SDK. Todo PR debe cumplir estos estándares.*
*Incumplen estas reglas → request changes. No se mergea sin cumplir.*
