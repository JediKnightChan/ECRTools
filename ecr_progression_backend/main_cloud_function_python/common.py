import typing
import logging
import itertools
from tools.s3_path_builder import S3PathBuilder


def batch_iterator(iterable, n):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


class AdminUser:
    """Types of admin users, which have absolute trust, opposite to player hosts"""

    SERVER = "server"
    BACKEND = "backend"


class APIAction:
    """List of API actions available for resource processors (specified in JSON body at field 'action')"""

    GET = "get"
    LIST = "list"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class APIPermission:
    """Specifies who can access this action for given player_id in action data. Backend can access any action"""

    ANYONE = "ANYONE"
    OWNING_PLAYER_ONLY = "OWNING_PLAYER_ONLY"
    SERVER_ONLY = "SERVER_ONLY"
    SERVER_OR_OWNING_PLAYER = "SERVER_OR_OWNING_PLAYER"


def permission_required(permission_type, player_arg_name="player"):
    """Permission wrapper around ResourceProcessor.API_PROCESS_REQUEST implementations"""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            can_perform_action = False
            logger = getattr(self, 'logger', None)

            asking_user = getattr(self, "user", None)
            target_user = args[0].get(player_arg_name)

            is_backend = asking_user == AdminUser.BACKEND
            is_server = asking_user == AdminUser.SERVER
            is_owning_player = asking_user == target_user

            if permission_type == APIPermission.ANYONE:
                can_perform_action = True
            elif permission_type == APIPermission.SERVER_ONLY:
                can_perform_action = is_server
            elif permission_type == APIPermission.OWNING_PLAYER_ONLY:
                can_perform_action = is_owning_player
            elif permission_type == APIPermission.SERVER_OR_OWNING_PLAYER:
                can_perform_action = is_server or is_owning_player

            if can_perform_action or is_backend:
                return func(self, *args, **kwargs)
            else:
                logger.warning(
                    f"Didn't allow asking user {asking_user} to perform action {self.__class__.__name__}->{func.__name__} with user {target_user}, args {args}")
                return {"error": "Not allowed to use this action"}, 403

        return wrapper

    return decorator


class ResourceProcessor:
    """Resource Processor is a handler (controller in MVC) for API request data per given resource (API entity)"""

    def __init__(self, logger, contour, user, yc, s3):
        """
        Constructor for ResourceProcessor

        :param logger: logger instance
        :param contour: dev/prod
        :param user: user who sent request (verified player account id or server or backend)
        :param yc: YDBConnector instance
        :param s3: S3Connector instance
        """

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

        self.contour = contour
        self.user = user
        self.s3_paths = S3PathBuilder(self.contour)

        self.s3 = s3
        self.yc = yc

    @property
    def action_not_allowed_response(self) -> typing.Tuple[dict, int]:
        return {"error": "Not allowed to use this action"}, 403

    @property
    def internal_server_error_response(self) -> typing.Tuple[dict, int]:
        return {"error": "Internal server error"}, 500

    def is_user_server_or_backend(self):
        """Checks if user who initiated request is server or backend, opposite to player host"""

        return str(self.user) in [AdminUser.SERVER, AdminUser.BACKEND]

    def get_table_name_for_contour(self, raw_table_name):
        """Returns a table name in the database for the current contour (prod with no suffix, dev with '_dev' suffix)"""

        if self.contour == "prod":
            return raw_table_name
        elif self.contour == "dev":
            return raw_table_name + "_dev"
        else:
            raise NotImplementedError

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
