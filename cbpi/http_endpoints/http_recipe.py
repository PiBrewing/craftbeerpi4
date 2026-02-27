from aiohttp import web
from cbpi.api import *
from cbpi.api.dataclasses import Props, Step
from cbpi.controller.recipe_controller import RecipeController
import logging

class RecipeHttpEndpoints:

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.controller: RecipeController = cbpi.recipe
        self.cbpi.register(self, "/recipe")

    @request_mapping(path="/", method="GET", auth_required=False)
    async def http_get_all(self, request):
        """
        ---
        description: Get all recipes from the craftbeerpi recipe book
        tags:
        - Recipe
        responses:
            "200":
                description: successful operation
        """
        return web.json_response(await self.controller.get_recipes())

    @request_mapping(path="/{name}", method="GET", auth_required=False)
    async def get_by_name(self, request):
        """
        ---
        description: Get recipe by file name from the craftbeerpi recipe book
        tags:
        - Recipe
        parameters:
        - name: "name"
          in: "path"
          description: "Recipe File Name"
          required: true
          type: "string"
        responses:
            "200":
                description: successful operation
        """
        name = request.match_info["name"]
        return web.json_response(await self.controller.get_by_name(name))

    @request_mapping(path="/create", method="POST", auth_required=False)
    async def http_create(self, request):
        """
        ---
        description: Add Recipe to the craftbeerpi recipe book
        tags:
        - Recipe
        parameters:
        - in: body
          name: body
          description: Create a new recipe with name
          required: true
          schema:
            type: object
            properties:
              name:
                type: string

        responses:
            "200":
                description: successful operation
        """
        data = await request.json()
        return web.json_response(
            dict(id=await self.controller.create(data.get("name")))
        )

    @request_mapping(path="/{name}", method="PUT", auth_required=False)
    async def http_save(self, request):
        """
        ---
        description: Save Recipe
        tags:
        - Recipe
        parameters:
        - name: "id"
          in: "path"
          description: "Recipe Id"
          required: true
          type: "string"
        - in: body
          name: body
          description: Recipe Data
          required: false
          schema:
            type: object

        responses:
            "200":
                description: successful operation
        """
        data = await request.json()
        name = request.match_info["name"]
        await self.controller.save(name, data)
        logging.error(data)
        return web.Response(status=204)

    @request_mapping(path="/{name}", method="DELETE", auth_required=False)
    async def http_remove(self, request):
        """
        ---
        description: Delete Recipe with given file name from the craftbeerpi recipe book
        tags:
        - Recipe
        parameters:
        - name: "id"
          in: "path"
          description: "Recipe File Name"
          required: true
          type: "string"

        responses:
            "200":
                description: successful operation
        """
        name = request.match_info["name"]
        await self.controller.remove(name)
        return web.Response(status=200)

    @request_mapping(path="/{name}/brew", method="POST", auth_required=False)
    async def http_brew(self, request):
        """
        ---
        description: Brew recipe with given file name from the craftbeerpi recipe book
        tags:
        - Recipe
        parameters:
        - name: "name"
          in: "path"
          description: "Recipe File Name"
          required: true
          type: "string"


        responses:
            "200":
                description: successful operation
        """
        name = request.match_info["name"]
        await self.controller.brew(name)
        return web.Response(status=200)

    @request_mapping(path="/{id}/clone", method="POST", auth_required=False)
    async def http_clone(self, request):
        """
        ---
        description: Brew
        tags:
        - Recipe
        parameters:
        - name: "id"
          in: "path"
          description: "Recipe Filename"
          required: true
          type: "string"
          example: 
            id: "EKCnCHwKgPkaEiK4s2aXh3"
        - in: body
          name: body
          description: Recipe Data
          required: false
          schema:
            type: object
            properties:
              name:
                type: string
            example:
              name: "My Cloned Recipe"

        responses:
            "200":
                description: successful operation
        """
        id = request.match_info["id"]
        data = await request.json()

        return web.json_response(
            dict(id=await self.controller.clone(id, data.get("name")))
        )
