import asyncio
import logging
import os
from datetime import datetime
from email import message

import shortuuid
from cbpi.api import *
from cbpi.api.dataclasses import NotificationType


class NotificationController:

    def __init__(self, cbpi):
        """
        :param cbpi: craftbeerpi object
        """
        self.cbpi = cbpi
        self.logger = logging.getLogger(__name__)
        logging.root.addFilter(self.notify_log_event)
        self.callback_cache = {}
        self.listener = {}
        self.notifications = []
        self.update_key = "notificationupdate"
        self.sorting = False
        self.check_startup_message()

    def check_startup_message(self):
        self.restore_error = self.cbpi.config_folder.get_file_path("restore_error.log")
        try:
            with open(self.restore_error) as f:
                for line in f:
                    self.notifications.insert(
                        0,
                        [
                            f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: Restore Error | {line}'
                        ],
                    )
            os.remove(self.restore_error)
        except Exception as e:
            pass

    def notify_log_event(self, record):
        NOTIFY_ON_ERROR = self.cbpi.config.get("NOTIFY_ON_ERROR", "No")
        if NOTIFY_ON_ERROR == "Yes":
            try:
                message = str(record.msg)
            except:
                message = record.msg
            try:
                if record.levelno > 20:
                    # on log events higher then INFO we want to notify all clients
                    type = NotificationType.WARNING
                    if record.levelno > 30:
                        type = NotificationType.ERROR
                    self.cbpi.notify(
                        title=f"{record.levelname}", message=message, type=type
                    )
            except Exception as e:
                pass
        return True

    def get_state(self):
        result = self.notifications
        return result

    def add_listener(self, method):
        listener_id = shortuuid.uuid()
        self.listener[listener_id] = method
        return listener_id

    def remove_listener(self, listener_id):
        try:
            del self.listener[listener_id]
        except:
            self.logger.error("Failed to remove listener {}".format(listener_id))

    async def _call_listener(self, title, message, type, action):
        background_tasks = set()
        for id, method in self.listener.items():
            task = asyncio.create_task(method(self.cbpi, title, message, type, action))
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

    def notify(
        self,
        title,
        message: str,
        type: NotificationType = NotificationType.INFO,
        action=[],
        timeout: int = 5000,
    ) -> None:
        """
        This is a convinience method to send notification to the client

        :param key: notification key
        :param message: notification message
        :param type: notification type (info,warning,danger,successs)
        :return:
        """
        notifcation_id = shortuuid.uuid()
        background_tasks = set()

        def prepare_action(item):
            item.id = shortuuid.uuid()
            return item.to_dict()

        actions = list(map(lambda item: prepare_action(item), action))
        self.callback_cache[notifcation_id] = action
        self.cbpi.ws.send(
            dict(
                id=notifcation_id,
                topic="notifiaction",
                type=type.value,
                title=title,
                message=message,
                action=actions,
                timeout=timeout,
            )
        )
        data = dict(
            type=type.value,
            title=title,
            message=message,
            action=actions,
            timeout=timeout,
        )
        self.cbpi.push_update(topic="cbpi/notification", data=data)
        self.notifications.insert(
            0, [f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {title} | {message}']
        )
        if len(self.notifications) > 100:
            self.notifications = self.notifications[:100]
        self.cbpi.ws.send(
            dict(topic=self.update_key, data=self.notifications), self.sorting
        )
        task = asyncio.create_task(self._call_listener(title, message, type, action))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    def delete_all_notifications(self):
        self.notifications = []
        self.cbpi.ws.send(
            dict(topic=self.update_key, data=self.notifications), self.sorting
        )

    def notify_callback(self, notification_id, action_id) -> None:
        try:
            action = next(
                (
                    item
                    for item in self.callback_cache[notification_id]
                    if item.id == action_id
                ),
                None,
            )
            if action.method is not None:
                background_tasks = set()
                task = asyncio.create_task(action.method())
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            del self.callback_cache[notification_id]
            return True
        except Exception as e:
            self.logger.error("Failed to call notification callback")
            return False    

