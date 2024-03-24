import typing
import logging

from tools.s3_connection import S3Connector
from tools.s3_path_builder import S3PathBuilder


class APIAction:
    GET = "get"
    LIST = "list"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class ResourceProcessor:
    """Resource Processor is a handler (controller in MVC) for API request data per given resource (API entity)"""

    def __init__(self, logger, contour):
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

        self.contour = contour
        self.s3 = S3Connector()
        self.s3_paths = S3PathBuilder(self.contour)

    @property
    def action_not_allowed_response(self) -> typing.Tuple[dict, int]:
        return {"error": "This action is not allowed"}, 400

    @property
    def internal_server_error_response(self) -> typing.Tuple[dict, int]:
        return {"error": "Internal server error"}, 500

    def API_PROCESS_REQUEST(self, action: str, request_body: dict) -> typing.Tuple[dict, int]:
        """Default entrypoint for processing API request"""

        if action == APIAction.GET:
            return self.API_GET(request_body)
        elif action == APIAction.LIST:
            return self.API_LIST(request_body)
        elif action == APIAction.CREATE:
            return self.API_CREATE(request_body)
        elif action == APIAction.MODIFY:
            return self.API_MODIFY(request_body)
        elif action == APIAction.DELETE:
            return self.API_DELETE(request_body)
        else:
            return self.API_CUSTOM_ACTION(action, request_body)

    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response

    def API_LIST(self, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response

    def API_CREATE(self, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response

    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response

    def API_DELETE(self, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response

    def API_CUSTOM_ACTION(self, action: str, request_body: dict) -> typing.Tuple[dict, int]:
        return self.action_not_allowed_response
