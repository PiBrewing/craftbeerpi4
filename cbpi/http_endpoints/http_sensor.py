import logging

from aiohttp import web
from cbpi.api import *
from cbpi.api.dataclasses import Props, Sensor

auth = False


class SensorHttpEndpoints:

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.controller = cbpi.sensor
        self.cbpi.register(self, "/sensor")

    @request_mapping(path="/", auth_required=False)
    async def http_get_all(self, request):
        """

        ---
        description: Switch actor on
        tags:
        - Sensor
        responses:
            "204":
                description: successful operation
        """
        return web.json_response(data=self.controller.get_state())

    @request_mapping(path="/", method="POST", auth_required=False)
    async def http_add(self, request):
        """
        ---
        description: add one Actor
        tags:
        - Sensor
        parameters:
        - in: body
          name: body
          description: Created an actor
          required: true

          schema:
            type: object

            properties:
              name:
                type: string
              type:
                type: string
              props:
                type: object
            example:
              name: "Actor 1"
              type: "CustomActor"
              props: {}

        responses:
            "204":
                description: successful operation
        """
        data = await request.json()
        sensor = Sensor(
            name=data.get("name"),
            props=Props(data.get("props", {})),
            type=data.get("type"),
        )
        response_data = await self.controller.add(sensor)

        return web.json_response(data=response_data.to_dict())

    @request_mapping(path="/{id}", method="PUT", auth_required=False)
    async def http_update(self, request):
        """
        ---
        description: Update an actor
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Actor ID"
          required: true
          type: "integer"
          format: "int64"
        - in: body
          name: body
          description: Update an actor
          required: false
          schema:
            type: object
            properties:
              name:
                type: string
              type:
                type: string
              config:
                props: object
        responses:
            "200":
                description: successful operation
        """
        id = request.match_info["id"]
        data = await request.json()
        sensor = Sensor(
            id=id,
            name=data.get("name"),
            props=Props(data.get("props", {})),
            type=data.get("type"),
        )
        return web.json_response(data=(await self.controller.update(sensor)).to_dict())

    @request_mapping(path="/{id}", method="DELETE", auth_required=False)
    async def http_delete_one(self, request):
        """
        ---
        description: Delete an actor
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Actor ID"
          required: true
          type: "string"
        responses:
            "204":
                description: successful operation
        """
        id = request.match_info["id"]
        await self.controller.delete(id)
        return web.Response(status=204)

    @request_mapping(path="/{id}/on", method="POST", auth_required=False)
    async def http_on(self, request) -> web.Response:
        """

        ---
        description: Switch actor on
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Actor ID"
          required: true
          type: "string"

        responses:
            "204":
                description: successful operation
            "405":
                description: invalid HTTP Met
        """
        id = request.match_info["id"]
        await self.controller.on(id)
        return web.Response(status=204)

    @request_mapping(path="/{id}/off", method="POST", auth_required=False)
    async def http_off(self, request) -> web.Response:
        """

        ---
        description: Switch actor on
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Actor ID"
          required: true
          type: "string"

        responses:
            "204":
                description: successful operation
            "405":
                description: invalid HTTP Met
        """
        id = request.match_info["id"]
        await self.controller.off(id)
        return web.Response(status=204)

    @request_mapping(path="/{id}", method="GET", auth_required=False)
    async def get_value(self, request):
        """

        ---
        description: Get Sensor Value
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Sensor ID"
          type: "string"
          required: true
        """
        id = request.match_info["id"]
        sensor_value = self.controller.get_sensor_value(id)
        logging.info(sensor_value)
        return web.json_response(data=sensor_value)

    @request_mapping(path="/{id}/action", method="POST", auth_required=auth)
    async def http_action(self, request) -> web.Response:
        """

        ---
        description: Call Action for Sensor
        tags:
        - Sensor
        parameters:
        - name: "id"
          in: "path"
          description: "Sensor ID"
          required: true
          type: "integer"
          format: "int64"
        - in: body
          name: body
          description: Call an action for a Sensor
          required: false
          schema:
            type: object
            properties:
              name:
                type: string
              parameter:
                type: object
        responses:
            "204":
                description: successful operation
        """
        sensor_id = request.match_info["id"]
        data = await request.json()
        # print(data)
        await self.controller.call_action(
            sensor_id, data.get("action"), data.get("parameter")
        )

        return web.Response(status=204)
