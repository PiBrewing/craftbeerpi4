import glob
import json
import os
import pathlib
import platform
import shutil
import zipfile
from ast import If, Try
from os import listdir
from os.path import isfile, join
from pathlib import Path


class ConfigFolder:
    def __init__(self, configFolderPath, logsFolderPath):
        self.configFolderPath = configFolderPath
        self.logsFolderPath = logsFolderPath
        print("config folder path :   " + configFolderPath)
        print("logs folder path   :   " + logsFolderPath)

    def config_file_exists(self, path):
        return os.path.exists(self.get_file_path(path))

    def get_file_path(self, file):
        return os.path.join(self.configFolderPath, file)

    def get_dashboard_path(self, file):
        return os.path.join(self.configFolderPath, "dashboard", file)

    def get_upload_file(self, file):
        return os.path.join(self.configFolderPath, "upload", file)

    def get_recipe_file_by_id(self, recipe_id):
        return os.path.join(
            self.configFolderPath, "recipes", "{}.yaml".format(recipe_id)
        )

    def get_fermenter_recipe_by_id(self, recipe_id):
        return os.path.join(
            self.configFolderPath, "fermenterrecipes", "{}.yaml".format(recipe_id)
        )

    def get_all_fermenter_recipes(self):
        fermenter_recipes_folder = os.path.join(
            self.configFolderPath, "fermenterrecipes"
        )
        fermenter_recipe_ids = [
            os.path.splitext(f)[0]
            for f in listdir(fermenter_recipes_folder)
            if isfile(join(fermenter_recipes_folder, f)) and f.endswith(".yaml")
        ]
        return fermenter_recipe_ids

    def check_for_setup(self):
        # is there a restored_config.zip file? if yes restore it first then delte the zip.
        backupfile = os.path.join(self.configFolderPath, "restored_config.zip")
        if os.path.exists(os.path.join(backupfile)) is True:
            print("***************************************************")
            print("Found backup of config. Starting restore")
            required_content = [
                "dashboard/",
                "recipes/",
                "upload/",
                "sensor.json",
                "actor.json",
                "kettle.json",
                "config.json",
                #'craftbeerpi.template',
                "chromium.desktop",
                "config.yaml",
            ]
            zip = zipfile.ZipFile(backupfile)
            zip_content_list = zip.namelist()
            zip_content = True
            missing_content = []
            print("Checking content of zip file")

            for content in required_content:
                try:
                    check = zip_content_list.index(content)
                except:
                    zip_content = False
                    missing_content.append(content)

            if zip_content == True:
                print("Found correct content. Starting Restore process")
                output_path = pathlib.Path(self.configFolderPath)
                system = platform.system()
                print(system)
                if system != "Windows":
                    owner = output_path.owner()
                    group = output_path.group()
                print("Removing old config folder")
                shutil.rmtree(output_path, ignore_errors=True)
                print("Extracting zip file to config folder")
                zip.extractall(output_path)
                zip.close()
                if system != "Windows":
                    print(
                        f"Changing owner and group of config folder recursively to {owner}:{group}"
                    )
                    self.recursive_chown(output_path, owner, group)
                print("Removing backup file")
                try:
                    os.remove(backupfile)
                except:
                    pass
                Line1 = "Contents of restored_config.zip file have been restored."
                Line2 = "In case of a partial backup you will still be prompted to run 'cbpi setup'."
                print(Line1)
                print(Line2)
            else:
                zip.close()
                Line1 = "Wrong Content in zip file. No restore possible"
                Line2 = f"These files are missing {missing_content}"
                print(Line1)
                print(Line2)
                restorelogfile = os.path.join(
                    self.configFolderPath, "restore_error.log"
                )
                f = open(restorelogfile, "w")
                f.write(Line1 + "\n")
                f.write(Line2 + "\n")
                f.close()

                print("renaming zip file so it will be ignored on the next start")
                try:
                    os.rename(
                        backupfile,
                        os.path.join(
                            self.configFolderPath, "UNRESTORABLE_restored_config.zip"
                        ),
                    )
                except:
                    print("renamed file does exist - deleting instead")
                    os.remove(backupfile)
            print("***************************************************")
        # possible restored_config.zip has been handeled now lets check if files and folders exist
        required_config_content = [
            ["config.yaml", "file"],
            ["actor.json", "file"],
            ["sensor.json", "file"],
            ["kettle.json", "file"],
            # ['fermenter_data.json', 'file'], created by fermentation_controller @ start if not available
            # ['step_data.json', 'file'],  created by step_controller @ start if not available
            ["config.json", "file"],
            ["craftbeerpi.template", "file"],
            ["chromium.desktop", "file"],
            ["dashboard", "folder"],
            ["dashboard/widgets", "folder"],
            ["fermenterrecipes", "folder"],
            [self.logsFolderPath, "folder"],
            ["recipes", "folder"],
            ["upload", "folder"],
            # ['dashboard/cbpi_dashboard_1.json', 'file'] no need to check - can be created with online editor
        ]
        for checking in required_config_content:
            if self.inform_missing_content(
                self.check_for_file_or_folder(
                    os.path.join(self.configFolderPath, checking[0]), checking[1]
                )
            ):
                # since there is no complete config we now check if the config folder may be completely empty to show hints:
                try:
                    if len(os.listdir(os.path.join(self.configFolderPath))) == 0:
                        print("***************************************************")
                        print(
                            f"the config folder '{self.configFolderPath}' seems to be completely empty"
                        )
                        print("you might want to run 'cbpi setup'.print")
                        print(
                            "but you could also place your zipped config backup named"
                        )
                        print(
                            "'restored_config.zip' inside the mentioned config folder for"
                        )
                        print("cbpi4 to automatically unpack it")
                        print("of course you can also place your config files manually")
                        print("***************************************************")
                    return False
                except:
                    print("***************************************************")
                    print("Cannot find config folder!")
                    print("Please navigate to path where you did run 'cbpi setup'.")
                    print("Or run 'cbpi setup' before starting the server.")
                    print("***************************************************")
                    return False

        # if cbpi_dashboard_1.json does'nt exist at the new location (configFolderPath/dashboard)
        # we move every cbpi_dashboard_n.json file from the old location (configFolderPath) there.
        # this could be a config zip file restore from version 4.0.7.a4 or prior.
        dashboard_1_path = os.path.join(
            self.configFolderPath, "dashboard", "cbpi_dashboard_1.json"
        )
        if (not (os.path.isfile(dashboard_1_path))) or self.check_for_empty_dashboard_1(
            dashboard_1_path
        ):
            for file in glob.glob(
                os.path.join(self.configFolderPath, "cbpi_dashboard_*.json")
            ):
                dashboardFile = os.path.basename(file)
                print(
                    f"Copy dashboard json file {dashboardFile} from config to config/dashboard folder"
                )
                shutil.move(
                    file,
                    os.path.join(self.configFolderPath, "dashboard", dashboardFile),
                )

    def check_for_empty_dashboard_1(self, dashboard_1_path):
        try:
            with open(dashboard_1_path, "r") as f:
                data = json.load(f)
            if (
                len(data["elements"]) == 0
            ):  # there may exist some paths but paths without elements in dashboard is not very likely
                return True
            else:
                return False
        except:  # file missing or bad json format
            return True

    def inform_missing_content(self, whatsmissing: str):
        if whatsmissing == "":
            return False
        # Starting with cbpi 4.2.0, the craftbeerpi.service file will be created dynamically from the template file based on the user id.
        # Therefore, the service file is replaced with a template file in the config folder
        if whatsmissing.find("craftbeerpi.template"):
            try:
                self.copyDefaultFileIfNotExists("craftbeerpi.template")
                return False
            except:
                pass
        print("***************************************************")
        print(f"CraftBeerPi config content not found: {whatsmissing}")
        print("Please run 'cbpi setup' before starting the server ")
        print("***************************************************")
        return True

    def check_for_file_or_folder(
        self, path: str, file_or_folder: str = ""
    ):  # file_or_folder should be "file" or "folder" or "" if both is ok
        if file_or_folder == "":  # file and folder is ok
            if os.path.exists(path):
                return ""
            else:
                return "file or folder missing: " + path
        if file_or_folder == "file":  # only file is ok
            if os.path.isfile(path):
                return ""
            else:
                return "file missing: " + path
        if file_or_folder == "folder":  # oly folder is ok
            if os.path.isdir(path):
                return ""
            else:
                return "folder missing: " + path
        return "usage of check_file_or_folder() function wrong. second Argument must either be 'file' or 'folder' or an empty string"

    def copyDefaultFileIfNotExists(self, file):
        if self.config_file_exists(file) is False:
            srcfile = os.path.join(os.path.dirname(__file__), "config", file)
            destfile = os.path.join(self.configFolderPath, file)
            shutil.copy(srcfile, destfile)

    def create_config_file(self):
        self.copyDefaultFileIfNotExists("config.yaml")
        self.copyDefaultFileIfNotExists("actor.json")
        self.copyDefaultFileIfNotExists("sensor.json")
        self.copyDefaultFileIfNotExists("kettle.json")
        self.copyDefaultFileIfNotExists("fermenter_data.json")
        self.copyDefaultFileIfNotExists("step_data.json")
        self.copyDefaultFileIfNotExists("config.json")
        self.copyDefaultFileIfNotExists("craftbeerpi.template")
        self.copyDefaultFileIfNotExists("chromium.desktop")

        print("Config Folder created")

    def create_home_folder_structure(configFolder):
        configFolder.create_folders()
        print("Folder created")

    def create_folders(self):
        pathlib.Path(self.configFolderPath).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.logsFolderPath).mkdir(parents=True, exist_ok=True)
        pathlib.Path(os.path.join(self.configFolderPath, "dashboard", "widgets")).mkdir(
            parents=True, exist_ok=True
        )
        pathlib.Path(os.path.join(self.configFolderPath, "recipes")).mkdir(
            parents=True, exist_ok=True
        )
        pathlib.Path(os.path.join(self.configFolderPath, "fermenterrecipes")).mkdir(
            parents=True, exist_ok=True
        )
        pathlib.Path(os.path.join(self.configFolderPath, "upload")).mkdir(
            parents=True, exist_ok=True
        )

    def recursive_chown(self, path, owner, group):
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                shutil.chown(dirpath, owner, group)
                for filename in filenames:
                    shutil.chown(os.path.join(dirpath, filename), owner, group)
        except:
            print("problems assigning file or folder permissions")
            print("if this happened on windows its fine")
            print(
                "if this happened in the dev container running inside windows its also fine but you might have to rebuild the container if you run into further problems"
            )
