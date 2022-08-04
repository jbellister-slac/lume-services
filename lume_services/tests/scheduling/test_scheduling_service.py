import prefect
import pytest

from prefect.utilities.backend import load_backend

from lume_services import config


class TestPrefectConfig:
    @pytest.fixture(autouse=True, scope="class")
    def _prepare(self, lume_services_settings):
        config.configure(lume_services_settings)

    @pytest.mark.usefixtures("_prepare")
    def test_prefect_config(self, lume_services_settings):
        prefect_config = lume_services_settings.prefect

        # check that server has been applied
        backend_spec = load_backend()
        assert backend_spec["backend"] == "server"

        # check assignment, has already been applied
        assert prefect.config.debug == prefect_config.debug
        assert prefect.config.home_dir == prefect_config.home_dir

        # check server values
        for key, value in prefect_config.server.dict().items():
            attr = getattr(prefect.config.server, key)
            assert attr == value

        # check ui values
        for key, value in prefect_config.ui.dict().items():
            attr = getattr(prefect.config.server.ui, key)
            assert attr == value

        # check graphql values
        for key, value in prefect_config.telemetry.dict().items():
            attr = getattr(prefect.config.server.telemetry, key)
            assert attr == value

    @pytest.mark.usefixtures("_prepare")
    def test_prefect_update_config(self, lume_services_settings):
        prefect_config = lume_services_settings.prefect

        new_config = prefect_config.copy()
        new_config.server.host = "0.0.0.0"
        new_config.server.host_port = 4000

        new_config.apply()

        # check server values
        for key, value in prefect_config.server.dict().items():
            attr = getattr(prefect.config.server, key)
            assert attr == value

        # check ui values
        for key, value in prefect_config.ui.dict().items():
            attr = getattr(prefect.config.server.ui, key)
            assert attr == value

        # check graphql values
        for key, value in prefect_config.telemetry.dict().items():
            attr = getattr(prefect.config.server.telemetry, key)
            assert attr == value


@pytest.mark.skip()
class TestSchedulingService:
    def test_init_service(self):
        ...

    def test_flow_of_flows_registration(self):
        ...
