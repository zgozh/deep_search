from utils.logger_utils import configure_project_logging

configure_project_logging()

from api.server import start_server

if __name__ == "__main__":
    start_server()
