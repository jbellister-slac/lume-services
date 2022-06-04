import pytest
import os
from sqlalchemy import create_engine
from string import Template
from datetime import datetime
import time
import mongomock
from mongoengine import connect

from lume_services.data.model.db.mysql import MySQLConfig, MySQLService
from lume_services.data.model.model_service import ModelService
from lume_services.data.results.db.db_service import DBServiceConfig
from lume_services.data.results.db.mongodb.service import MongodbService
from lume_services.data.results.results_service import (
    ResultsService,
    ResultsServiceConfig,
)

from lume_services.data.file.systems.local import LocalFilesystem
from lume_services.data.file.service import FileService

from lume_services.data.results.db.mongodb.models import ModelDocs as MongoDBModelDocs
from lume_services.tests.plugins.mysql import mysql_proc

from lume_services.context import Context, LUMEServicesConfig

from lume.serializers.base import SerializerBase


def pytest_addoption(parser):

    parser.addini("mysql_host", default="127.0.0.1", help="MySQL host")
    parser.addini("mysql_port", default=3306, help="MySQL port")
    parser.addini("mysql_user", default="root", help="MySQL user")
    parser.addini("mysql_passwd", default="root", help="MySQL password")
    parser.addini(name="mysql_dbname", help="Mysql database name", default="test")
    parser.addini(name="mysql_params", help="MySQL params", default="")
    parser.addini("mysql_database", default="model_db", help="Model database name")
    parser.addini("mysql_poolsize", default=1, help="MySQL client poolsize")
    parser.addini(name="mysql_mysqld", help="mysqld command", default="mysqld")
    parser.addini(
        name="mysql_mysqld_safe", help="mysqld safe command", default="mysqld_safe"
    )
    parser.addini(name="mysql_admin", help="mysql admin command", default="mysqladmin")
    parser.addini(
        name="mysql_logsdir",
        help="Add log directory",
    )
    parser.addini(
        name="mysql_install_db",
        help="Installation path",
        default="mysql_install_db",
    )


@pytest.fixture(scope="session", autouse=True)
def mysql_user(request):
    return request.config.getini("mysql_user")


@pytest.fixture(scope="session", autouse=True)
def mysql_host(request):
    return request.config.getini("mysql_host")


@pytest.fixture(scope="session", autouse=True)
def mysql_port(request):
    return int(request.config.getini("mysql_port"))


@pytest.fixture(scope="session", autouse=True)
def mysql_database(request):
    return request.config.getini("mysql_database")


@pytest.fixture(scope="session", autouse=True)
def mysql_pool_size(request):
    return int(request.config.getini("mysql_poolsize"))


@pytest.fixture(scope="session", autouse=True)
def base_db_uri(mysql_user, mysql_host, mysql_port):
    return Template("mysql+pymysql://${user}:@${host}:${port}").substitute(
        user=mysql_user, host=mysql_host, port=mysql_port
    )


mysql_server = mysql_proc()


@pytest.fixture(scope="session", autouse=True)
def mysql_config(mysql_user, mysql_host, mysql_port, mysql_database, mysql_pool_size):

    db_uri = Template(
        "mysql+pymysql://${user}:@${host}:${port}/${database}"
    ).substitute(
        user=mysql_user, host=mysql_host, port=mysql_port, database=mysql_database
    )

    return MySQLConfig(
        db_uri=db_uri,
        pool_size=mysql_pool_size,
    )


@pytest.mark.usefixtures("mysql_server")
@pytest.fixture(scope="module", autouse=True)
def mysql_service(mysql_config):
    mysql_service = MySQLService(mysql_config)
    return mysql_service


@pytest.fixture(scope="session")
def model_docs():
    return MongoDBModelDocs


@pytest.mark.usefixtures("mysql_server")
@pytest.fixture(scope="module", autouse=True)
def model_service(mysql_service, mysql_database, base_db_uri, mysql_server):

    # start the mysql process if not started
    if not mysql_server.running():
        mysql_server.start()

    # allow a moment for startup
    time.sleep(2)

    engine = create_engine(base_db_uri, pool_size=1)
    with engine.connect() as connection:
        connection.execute("CREATE DATABASE IF NOT EXISTS model_db;")

    model_service = ModelService(mysql_service)
    model_service.apply_schema()

    # set up database
    yield model_service

    with engine.connect() as connection:
        connection.execute(f"DROP DATABASE {mysql_database};")


class MongomockResultsDBConfig(DBServiceConfig):
    host: str = "mongomock://localhost"
    db: str = "test"
    port: int = 27017


@pytest.fixture(scope="session", autouse=True)
def mongodb_config():
    return MongomockResultsDBConfig()


@mongomock.patch(servers=(("localhost", 27017),))
@pytest.fixture(scope="module", autouse=True)
def mongodb_service(mongodb_config):
    return MongodbService(mongodb_config)


@pytest.fixture(scope="module", autouse=True)
def results_service(mongodb_service, model_docs):

    results_service = ResultsService(mongodb_service, model_docs)

    yield results_service

    cxn = connect("test", host="mongomock://localhost")
    cxn.drop_database("test")


@pytest.fixture(scope="module", autouse=True)
def local_filesystem_handler():
    return LocalFilesystem()


class TextSerializer(SerializerBase):
    def serialize(self, filename, text):

        with open(filename, "w") as f:
            f.write(text)

    @classmethod
    def deserialize(cls, filename):

        text = ""

        with open(filename, "r") as f:
            text = f.read()

        return text


@pytest.fixture(scope="module", autouse=True)
def text_serializer():
    return TextSerializer()


@pytest.fixture(scope="module")
def file_service(local_filesystem_handler):
    filesystems = [local_filesystem_handler]

    return FileService(filesystems)


@pytest.fixture(scope="module")
def context(
    mongodb_service,
    mysql_service,
    mysql_config,
    mongodb_config,
    model_docs,
    file_service,
):
    # don't use factory here because want to use pytest fixture management

    results_service_config = ResultsServiceConfig(
        model_docs=model_docs,
    )

    config = LUMEServicesConfig(
        results_service_config=results_service_config,
        model_db_service_config=mysql_config,
        results_db_service_config=mongodb_config,
    )

    context = Context(
        results_db_service=mongodb_service,
        model_db_service=mysql_service,
        file_service=file_service,
    )

    context.config.from_pydantic(config)

    return context


@pytest.fixture(scope="session", autouse=True)
def test_generic_result_document():
    return {
        "flow_id": "test_flow_id",
        "inputs": {"input1": 2.0, "input2": [1, 2, 3, 4, 5], "input3": "my_file.txt"},
        "outputs": {
            "output1": 2.0,
            "output2": [1, 2, 3, 4, 5],
            "ouptut3": "my_file.txt",
        },
    }


@pytest.fixture(scope="module", autouse=True)
def test_impact_result_document():
    return {
        "flow_id": "test_flow_id",
        "inputs": {"input1": 2.0, "input2": [1, 2, 3, 4, 5], "input3": "my_file.txt"},
        "outputs": {
            "output1": 2.0,
            "output2": [1, 2, 3, 4, 5],
            "ouptut3": "my_file.txt",
        },
        "plot_file": "my_plot_file.txt",
        "archive": "archive_file.txt",
        "pv_collection_isotime": datetime.now(),
        "config": {"config1": 1, "config2": 2},
    }


from glob import glob


def refactor(string: str) -> str:
    return string.replace("/", ".").replace("\\", ".").replace(".py", "")


pytest_plugins = [
    refactor(fixture)
    for fixture in glob("lume_services/tests/fixtures/*.py")
    if "__" not in fixture
]
