"""Ephemeral PYTHONPATH bootstrap; no production files modified."""
import os
if os.environ.get("OPENGTM_M0_FIXTURE") == "owned-ephemeral-v1":
    try:
        import importlib.abc
        import importlib.machinery
        import sys
        import socket
        from urllib.parse import urlparse
        url = urlparse(os.environ.get("DATABASE_URL", ""))
        if url.hostname != "postgres" or not (url.path or "").startswith("/m0_owned_"):
            os._exit(72)
        if os.environ.get("M0_INTERNAL_NETWORK_ATTESTATION") != "isolated-no-egress":
            os._exit(73)
        # Defense in depth only: container internal networking is independently required.
        allowed_ips = {item[4][0] for item in socket.getaddrinfo("postgres", 5432)}
        original_connect = socket.socket.connect
        def connect(self, address):
            if isinstance(address, tuple) and (address[1] != 5432 or address[0] not in allowed_ips | {"postgres"}):
                raise RuntimeError("M0 outbound connection denied")
            return original_connect(self, address)
        socket.socket.connect = connect
        original_connect_ex = socket.socket.connect_ex
        def connect_ex(self, address):
            if isinstance(address, tuple) and (address[1] != 5432 or address[0] not in allowed_ips | {"postgres"}):
                raise RuntimeError("M0 outbound connection denied")
            return original_connect_ex(self, address)
        socket.socket.connect_ex = connect_ex
        targets = {"apps.api.services.workbook.providers", "apps.api.services.workbook.provider_runner"}
        class FixtureLoader(importlib.abc.Loader):
            def __init__(self, loader): self.loader = loader
            def create_module(self, spec): return self.loader.create_module(spec)
            def exec_module(self, module):
                self.loader.exec_module(module)
                if module.__name__.endswith("provider_runner"):
                    from simulator import provider_job
                    module._provider_job = provider_job
                else:
                    from apps.api.services.leadgen.enrichment.provider import EnrichmentProvider, EnrichmentResult
                    class FixtureProvider(EnrichmentProvider):
                        name = "hunter_io"
                        capabilities = ["email"]
                        async def enrich(self, lead):
                            raise RuntimeError("fixture must use native killable provider pool")
                    module._registry = {"hunter_io": FixtureProvider()}
        class FixtureFinder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname not in targets: return None
                spec = importlib.machinery.PathFinder.find_spec(fullname, path)
                if spec and spec.loader: spec.loader = FixtureLoader(spec.loader)
                return spec
        sys.meta_path.insert(0, FixtureFinder())
    except BaseException:
        os._exit(74)
