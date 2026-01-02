import logging
import os
import sys
from pathlib import Path
from zipfile import ZipFile

import requests
from cbpi import __codename__, __version__
from cbpi.configFolder import ConfigFolder
from cbpi.craftbeerpi import CraftBeerPi
from cbpi.utils.utils import load_config

try:
    import pwd

    module_pwd = True
except:
    module_pwd = False
import importlib
import pathlib
import pkgutil
import platform
import shutil
import time
from subprocess import call

import click
import distro
import inquirer
from colorama import Back, Fore, Style
from importlib_metadata import metadata
from tabulate import tabulate


class CraftBeerPiCli:
    def __init__(self, config) -> None:
        self.config = config
        pass

    def setup(self):
        print("Setting up CraftBeerPi")
        self.config.create_home_folder_structure()
        self.config.create_config_file()

    def start(self):
        if self.config.check_for_setup() is False:
            return
        print("START")
        cbpi = CraftBeerPi(self.config)
        cbpi.start()

    def setup_one_wire(self):
        print("Setting up 1Wire")
        with open("/boot/firmware/config.txt", "r") as f:
            lines = f.readlines()
        if "dtoverlay=w1-gpio,gpiopin=4,pullup=on\n" not in lines:    
            lines.append("dtoverlay=w1-gpio,gpiopin=4,pullup=on\n")

        configtempfile = os.path.join(self.config.get_file_path(""), "config.txt")

        with open(configtempfile, "w") as f:
            for line in lines:
                f.write(line)
        destfile = "/boot/firmware/config.txt"

        # copy and remove afterwards as mv will work, but raise an error message due to different file owners
        shutil.os.system('sudo cp "{}" "{}"'.format(configtempfile, destfile))
        shutil.os.system('rm -rf "{}"'.format(configtempfile))

        print("/boot/firmware/config.txt created")

    def list_one_wire(self):
        print("List 1Wire")
        call(["sudo", "modprobe", "w1-gpio"])
        call(["sudo", "modprobe", "w1-therm"])
        try:
            for dirname in os.listdir("/sys/bus/w1/devices"):
                if dirname.startswith("28") or dirname.startswith("10"):
                    print(dirname)
        except Exception as e:
            print(e)

    def plugins_list(self):
        result = []
        print("")
        print(Fore.LIGHTYELLOW_EX, "List of active plugins", Style.RESET_ALL)
        print("")
        discovered_plugins = {
            name: importlib.import_module(name)
            for finder, name, ispkg in pkgutil.iter_modules()
            if name.startswith("cbpi") and len(name) > 4
        }
        for key, module in discovered_plugins.items():
            try:
                meta = metadata(key)
                result.append(
                    dict(
                        Name=meta["Name"],
                        Version=meta["Version"],
                        Author=meta["Author"],
                        Homepage=meta["Home-page"],
                        Summary=meta["Summary"],
                    )
                )

            except Exception as e:
                print(e)
        print(Fore.LIGHTGREEN_EX, tabulate(result, headers="keys"), Style.RESET_ALL)

    def plugin_create(self, pluginName):
        print("Plugin Creation")
        print("")

        questions = [
            inquirer.Text(
                "name",
                message='Plugin Name (will be prefixed with "cbpi4-")',
                default=pluginName,
            ),
        ]

        answers = inquirer.prompt(questions)

        if answers["name"] == "":
            print("you failed to provide a name for the new plugin - terminating")
            return

        name = "cbpi4-" + str(answers["name"]).replace("_", "-").replace(" ", "-")
        if os.path.exists(os.path.join(".", name)) is True:
            print("Cant create Plugin. Folder {} already exists ".format(name))
            return

        url = (
            "https://github.com/PiBrewing/craftbeerpi4-plugin-template/archive/main.zip"
        )
        r = requests.get(url)
        with open("temp.zip", "wb") as f:
            f.write(r.content)

        with ZipFile("temp.zip", "r") as repo_zip:
            repo_zip.extractall()

        time.sleep(4)  # windows dev container permissions problem otherwise

        os.rename(
            os.path.join(".", "craftbeerpi4-plugin-template-main"),
            os.path.join(".", name),
        )
        os.rename(os.path.join(".", name, "src"), os.path.join(".", name, name))

        import jinja2

        templateLoader = jinja2.FileSystemLoader(searchpath=os.path.join(".", name))
        templateEnv = jinja2.Environment(loader=templateLoader)
        TEMPLATE_FILE = "setup.py"
        template = templateEnv.get_template(TEMPLATE_FILE)
        outputText = template.render(name=name)

        with open(os.path.join(".", name, "setup.py"), "w") as fh:
            fh.write(outputText)

        TEMPLATE_FILE = "MANIFEST.in"
        template = templateEnv.get_template(TEMPLATE_FILE)
        outputText = template.render(name=name)
        with open(os.path.join(".", name, "MANIFEST.in"), "w") as fh:
            fh.write(outputText)

        TEMPLATE_FILE = os.path.join("/", name, "config.yaml")
        operatingsystem = str(platform.system()).lower()
        if operatingsystem.startswith("win"):
            TEMPLATE_FILE = str(TEMPLATE_FILE).replace("\\", "/")

        template = templateEnv.get_template(TEMPLATE_FILE)
        outputText = template.render(name=name)

        with open(os.path.join(".", name, name, "config.yaml"), "w") as fh:
            fh.write(outputText)

        print("")
        print("")
        print(
            "Plugin {}{}{} created! ".format(Fore.LIGHTGREEN_EX, name, Style.RESET_ALL)
        )
        print("")
        print(
            "Developer Documentation: https://openbrewing.gitbook.io/craftbeerpi4_support/readme/development"
        )
        print("")
        print("Happy developing! Cheers")
        print("")
        print("")

    def autostart(self, name):
        """Enable or disable autostart"""
        if name == "status":
            if (
                os.path.exists(
                    os.path.join("/etc/systemd/system", "craftbeerpi.service")
                )
                is True
            ):
                print(
                    "CraftBeerPi Autostart is {}ON{}".format(
                        Fore.LIGHTGREEN_EX, Style.RESET_ALL
                    )
                )
            else:
                print(
                    "CraftBeerPi Autostart is {}OFF{}".format(Fore.RED, Style.RESET_ALL)
                )
        elif name == "on":
            # user=os.getlogin()
            user = pwd.getpwuid(os.getuid()).pw_name
            path = "/usr/local/bin/cbpi"
            if os.path.exists("/home/" + user + "/.local/bin/cbpi") is True:
                path = "/home/" + user + "/.local/bin/cbpi"
            print("Add craftbeerpi.service to systemd")
            try:
                if (
                    os.path.exists(
                        os.path.join("/etc/systemd/system", "craftbeerpi.service")
                    )
                    is False
                ):
                    templatefile = self.config.get_file_path("craftbeerpi.template")
                    shutil.os.system(
                        'cp "{}" "{}"'.format(
                            templatefile,
                            self.config.get_file_path("craftbeerpi.service"),
                        )
                    )
                    srcfile = self.config.get_file_path("craftbeerpi.service")
                    import jinja2

                    templateLoader = jinja2.FileSystemLoader(
                        searchpath=os.path.join(self.config.get_file_path(""))
                    )
                    templateEnv = jinja2.Environment(loader=templateLoader)
                    operatingsystem = str(platform.system()).lower()
                    if operatingsystem.startswith("win"):
                        srcfile = str(srcfile).replace("\\", "/")

                    template = templateEnv.get_template("craftbeerpi.service")
                    outputText = template.render(user=user, path=path)
                    with open(srcfile, "w") as fh:
                        fh.write(outputText)
                    destfile = os.path.join("/etc/systemd/system")
                    shutil.os.system('sudo mv "{}" "{}"'.format(srcfile, destfile))
                    print("Copied craftbeerpi.service to /etc/systemd/system")
                    shutil.os.system("sudo systemctl enable craftbeerpi.service")
                    print("Enabled craftbeerpi service")
                    shutil.os.system("sudo systemctl start craftbeerpi.service")
                    print("Started craftbeerpi.service")
                else:
                    print(
                        "craftbeerpi.service is already located in /etc/systemd/system"
                    )
            except Exception as e:
                print(e)
                return
            return
        elif name == "off":
            print("Remove craftbeerpi.service from systemd")
            try:
                status = os.popen(
                    "systemctl list-units --type=service --state=running | grep craftbeerpi.service"
                ).read()
                if status.find("craftbeerpi.service") != -1:
                    shutil.os.system("sudo systemctl stop craftbeerpi.service")
                    print("Stopped craftbeerpi service")
                    shutil.os.system("sudo systemctl disable craftbeerpi.service")
                    print("Removed craftbeerpi.service as service")
                else:
                    print("craftbeerpi.service service is not running")

                if (
                    os.path.exists(
                        os.path.join("/etc/systemd/system", "craftbeerpi.service")
                    )
                    is True
                ):
                    shutil.os.system(
                        'sudo rm -rf "{}"'.format(
                            os.path.join("/etc/systemd/system", "craftbeerpi.service")
                        )
                    )
                    print("Deleted craftbeerpi.service from /etc/systemd/system")
                else:
                    print("craftbeerpi.service is not located in /etc/systemd/system")
            except Exception as e:
                print(e)
                return
            return

    def chromium(self, name, width=None, height=None):
        try:
            version = int(distro.version())
        except:
            version = 0

        if version < 13:
            """Enable or disable autostart"""
            if name == "status":
                if (
                    os.path.exists(os.path.join("/etc/xdg/autostart/", "chromium.desktop"))
                    is True
                ):
                    print(
                        "CraftBeerPi Chromium Desktop is {}ON{}".format(
                            Fore.LIGHTGREEN_EX, Style.RESET_ALL
                        )
                    )
                else:
                    print(
                        "CraftBeerPi Chromium Desktop is {}OFF{}".format(
                            Fore.RED, Style.RESET_ALL
                        )
                    )
            elif name == "on":
                print("Add chromium.desktop to /etc/xdg/autostart/")
                try:
                    if (
                        os.path.exists(
                            os.path.join("/etc/xdg/autostart/", "chromium.desktop")
                        )
                        is False
                    ):
                        srcfile = self.config.get_file_path("chromium.desktop")
                        destfile = os.path.join("/etc/xdg/autostart/")
                        shutil.os.system('sudo cp "{}" "{}"'.format(srcfile, destfile))
                        print("Copied chromium.desktop to /etc/xdg/autostart/")
                    else:
                        print("chromium.desktop is already located in /etc/xdg/autostart/")
                except Exception as e:
                    print(e)
                    return
                return
            elif name == "off":
                print("Remove chromium.desktop from /etc/xdg/autostart/")
                try:
                    if (
                        os.path.exists(
                            os.path.join("/etc/xdg/autostart/", "chromium.desktop")
                        )
                        is True
                    ):
                        shutil.os.system(
                            'sudo rm -rf "{}"'.format(
                                os.path.join("/etc/xdg/autostart/", "chromium.desktop")
                            )
                        )
                        print("Deleted chromium.desktop from /etc/xdg/autostart/")
                    else:
                        print("chromium.desktop is not located in /etc/xdg/autostart/")
                except Exception as e:
                    print(e)
                    return
                return
        else:
            user = pwd.getpwuid(os.getuid()).pw_name
            file = "/home/" + user + "/.config/labwc/autostart"

            if name == "status":
                if os.path.exists(file) is False:
                    print(
                        "CraftBeerPi Chromium Autostart is {}OFF{}".format(
                            Fore.RED, Style.RESET_ALL
                        )
                    )
                    return
                with open(file, "r") as f:
                    lines = f.readlines()
                    chromiumfound = False
                    for line in lines:
                        if line.find("chromium") != -1:
                            chromiumfound = True
                    if chromiumfound is True:
                        print(
                                "CraftBeerPi Chromium Autostart is {}ON{}".format(
                                    Fore.LIGHTGREEN_EX, Style.RESET_ALL
                                )
                            )
                    else:
                        print(
                                "CraftBeerPi Chromium Autostart is {}OFF{}".format(
                                    Fore.RED, Style.RESET_ALL
                                )
                            )
                    return
                pass
            elif name == "on":
                print("Add chromium to labwc autostart")
                if width is not None and height is not None:
                    command='chromium = /usr/bin/chromium  --start-maximized --start-fullscreen --window-size={},{} --password-store=basic --app=http://localhost:8000'.format(width, height)
                else:
                    command='chromium = /usr/bin/chromium --start-maximized --start-fullscreen --password-store=basic --app=http://localhost:8000'
                try:
                    if os.path.exists(file) is False:
                        pathlib.Path(file).mkdir(parents=True, exist_ok=True)
                        with open(file, "a") as f:
                            f.write(command)
                        print("Added chromium to labwc autostart")
                        print(
                                "CraftBeerPi Chromium Autostart is {}ON{}".format(
                                    Fore.LIGHTGREEN_EX, Style.RESET_ALL
                                )
                            )
                    else:
                        print("labwc autostart file already exists")
                        with open(file, "r") as f:
                            lines = f.readlines()
                            chromiumfound = False
                            for line in lines:
                                if line.find("chromium") != -1:
                                    chromiumfound = True
                            if chromiumfound is True:
                                print("chromium is already in the autostart file")
                                print(
                                "CraftBeerPi Chromium Autostart is {}ON{}".format(
                                    Fore.LIGHTGREEN_EX, Style.RESET_ALL
                                )
                            )
                                return
                            else:
                                with open(file, "a") as f:
                                    f.write(command)
                                print("Added chromium to labwc autostart")
                                print(
                                    "CraftBeerPi Chromium Autostart is {}ON{}".format(
                                        Fore.LIGHTGREEN_EX, Style.RESET_ALL
                                    )   
                                )
                except Exception as e:
                    print(e)
                    return
            elif name == "off":
                print("Remove chromium from labwc autostart")
                try:
                    if os.path.exists(file) is False:
                        print("labwc autostart file does not exist")
                        print(
                                "CraftBeerPi Chromium Autostart is {}OFF{}".format(
                                    Fore.RED, Style.RESET_ALL
                                )
                            )                        
                        return
                    with open(file, "r") as f:
                        lines = f.readlines()
                    with open(file, "w") as f:
                        for line in lines:
                            if line.find("chromium") == -1:
                                f.write(line)
                    print("Removed chromium from labwc autostart")
                    print(
                                "CraftBeerPi Chromium Autostart is {}OFF{}".format(
                                    Fore.RED, Style.RESET_ALL
                                )
                            )
                except Exception as e:
                    print(e)
                    return        
        



@click.group()
@click.pass_context
@click.option(
    "--config-folder-path",
    "-c",
    default="./config",
    type=click.Path(),
    help="Specify where the config folder is located. Defaults to './config'.",
)
@click.option(
    "--logs-folder-path",
    "-l",
    default="",
    type=click.Path(),
    help="Specify where the log folder is located. Defaults to '../logs' relative from the config folder.",
)
@click.option(
    "--debug-log-level",
    "-d",
    default="99",
    type=int,
    help="Specify the log level you want to write to all logs. 0=ALL, 10=DEBUG, 20=INFO 30(default)=WARNING, 40=ERROR, 50=CRITICAL. Can be also set in config.yaml (debug-log-level: INT)",
)
def main(context, config_folder_path, logs_folder_path, debug_log_level):
    print("--------------------------")
    print("Welcome to CBPi " + __version__)
    print("--------------------------")
    if logs_folder_path == "":
        logs_folder_path = os.path.join(
            Path(config_folder_path).absolute().parent, "logs"
        )
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    config = ConfigFolder(config_folder_path, logs_folder_path)
    static_config = load_config(config.get_file_path("config.yaml"))
    try:
        if debug_log_level == 99:
            debug_log_level = static_config["debug-log-level"]
    except:
        debug_log_level = 30

    logging.basicConfig(format=formatter, stream=logging.StreamHandler())
    logger = logging.getLogger()
    print("*******************************")
    print("Debug-log-level is {}".format(debug_log_level))
    print("*******************************")
    logger.setLevel(debug_log_level)
    try:
        if not os.path.isdir(logs_folder_path):
            logger.info(
                f"logs folder '{logs_folder_path}' doesnt exist and we are trying to create it"
            )
            pathlib.Path(logs_folder_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"logs folder '{logs_folder_path}' successfully created")
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(logs_folder_path, f"cbpi.log"), maxBytes=1000000, backupCount=3
        )
        logger.addHandler(handler)
        handler.setFormatter(formatter)
    except Exception as e:
        logger.warning(
            "log folder or log file could not be created or accessed. check folder and file permissions or create the logs folder somewhere you have access with a start option like '--log-folder-path=./logs'"
        )
        try:
            logger.warning(
                "Trying to set rights for cbpi user on the log folder and file"
            )
            user = pwd.getpwuid(os.getuid()).pw_name
            shutil.os.system(f'sudo chown -R {user}:{user} {logs_folder_path}')
            handler = logging.handlers.RotatingFileHandler(
                os.path.join(logs_folder_path, f"cbpi.log"), maxBytes=1000000, backupCount=3
            )
            logger.addHandler(handler)
            handler.setFormatter(formatter)
        except Exception as e:
            logging.critical(e, exc_info=True)
    
    cbpi_cli = CraftBeerPiCli(config)
    context.obj = cbpi_cli


@main.command()
@click.pass_context
def setup(context):
    """Create Config folder"""
    context.obj.setup()


@main.command()
@click.pass_context
@click.option("--list", is_flag=True, help="List all 1Wire Devices")
@click.option("--setup", is_flag=True, help="Setup 1Wire on Raspberry Pi")
def onewire(context, list, setup):
    """(--setup | --list) Setup 1wire on Raspberry Pi or list sensors"""
    operationsystem = sys.platform
    if not operationsystem.startswith("win"):
        if setup is True:
            context.obj.setup_one_wire()
        if list is True:
            context.obj.list_one_wire()
    else:
        print("Onewire options NOT available under Windows")


@main.command()
@click.pass_context
def start(context):
    context.obj.start()


@main.command()
@click.pass_context
def plugins(context):
    """List active plugins"""
    context.obj.plugins_list()


@main.command()
@click.pass_context
@click.argument("pluginname", nargs=-1, required=False)
def create(context, pluginname=[]):
    """Create New Plugin"""
    sentence = ""
    for word in pluginname:
        if sentence != "":
            sentence += " "
        sentence += word
    context.obj.plugin_create(sentence)


@main.command()
@click.pass_context
@click.argument("name")
def autostart(context, name):
    """(on|off|status) Enable or disable autostart"""
    operationsystem = sys.platform
    if not operationsystem.startswith("win"):
        context.obj.autostart(name)
    else:
        print("Autostart option NOT available under Windows")


@main.command()
@click.pass_context
@click.argument("name")
@click.option("--resolution", nargs=2, type=int, help="Optional for on:Set the chromium resolution for fullscreen mode (width height)")
def chromium(context, name, resolution):
    """(on|off|status) Enable or disable Kiosk mode"""
    operationsystem = sys.platform
    if not operationsystem.startswith("win"):
        if resolution is not None and name == "on":
            width = resolution[0]
            height = resolution[1]
            print("Set screen resolution to {}x{}".format(width, height))
            context.obj.chromium(name, width, height)
        else:
            context.obj.chromium(name)
    else:
        print("Chromium option NOT available under Windows")
