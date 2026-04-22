from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Our FHIR server base URL (ngrok)
    fhir_base_url: str = "https://ngrok.headease.nl/fhir"

    # LRZa (adressering) base URL
    lrza_base_url: str = "https://adressering.proeftuin.gf.irealisatie.nl/poc/FHIR/fhir"

    # NVI (nationale verwijsindex) base URL
    nvi_base_url: str = "https://nvi.proeftuin.gf.irealisatie.nl"

    # PRS (pseudonymisation) base URL
    prs_base_url: str = "https://pseudoniemendienst.proeftuin.gf.irealisatie.nl"

    # OAuth server
    oauth_base_url: str = "https://oauth.proeftuin.gf.irealisatie.nl"

    # Organization identifiers
    ura_number: str = "90000315"
    organization_name: str = "HeadEase"
    nvi_ura_number: str = "90000901"

    # Client certificates — relative to project root
    # UZI cert: used for signing JWTs (contains URA number)
    client_cert: Path = Path("certificates/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi-chain.crt")
    client_key: Path = Path("certificates/headease_nvi_20260202_145627.key")
    # UZI single cert (for x5c header)
    uzi_cert: Path = Path("certificates/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi.crt")
    uzi_intermediate_cert: Path = Path("certificates/gfmodules-test-uzi-external-intermediate.cer")
    # LDN cert: used for mTLS connections (thumbprint in JWT cnf)
    ldn_cert: Path = Path("certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn.crt")
    ldn_chain_cert: Path = Path("certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn-chain.crt")

    model_config = {"env_prefix": "HEADEASE_", "env_file": ".env"}

    @property
    def client_cert_path(self) -> Path:
        return self.client_cert if self.client_cert.is_absolute() else PROJECT_ROOT / self.client_cert

    @property
    def client_key_path(self) -> Path:
        return self.client_key if self.client_key.is_absolute() else PROJECT_ROOT / self.client_key

    def _resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def uzi_cert_path(self) -> Path:
        return self._resolve(self.uzi_cert)

    @property
    def uzi_intermediate_cert_path(self) -> Path:
        return self._resolve(self.uzi_intermediate_cert)

    @property
    def ldn_cert_path(self) -> Path:
        return self._resolve(self.ldn_cert)

    @property
    def ldn_chain_cert_path(self) -> Path:
        return self._resolve(self.ldn_chain_cert)


settings = Settings()
