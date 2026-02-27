from aiohttp import web
from cbpi.api import request_mapping
from cbpi.utils import json_dumps


class NotificationHttpEndpoints:

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.cbpi.register(self, url_prefix="/notification")

    @request_mapping(
        path="/{id}/action/{action_id}", method="POST", auth_required=False
    )
    async def action(self, request):
        """
        ---
        description: Update an actor
        tags:
        - Notification
        parameters:
        - name: "id"
          in: "path"
          description: "Notification Id"
          required: true
          type: "string"
        - name: "action_id"
          in: "path"
          description: "Action Id"
          required: true
          type: "string"

        responses:
            "200":
                description: successful operation
            "400":
                description: failed operation
        """

        notification_id = request.match_info["id"]
        action_id = request.match_info["action_id"]
        # print(notification_id, action_id)
        success = self.cbpi.notification.notify_callback(notification_id, action_id)
        return web.Response(status=200 if success else 400)

    @request_mapping("/delete", method="POST", auth_required=False)
    async def restart(self, request):
        """
        ---
        description: DeleteNotifications
        tags:
        - Notification
        responses:
            "200":
                description: successful operation
        """
        self.cbpi.notification.delete_all_notifications()
        return web.Response(status=200)
