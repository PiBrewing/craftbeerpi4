import logging
import requests
import yaml
from cbpi.configFolder import ConfigFolder
from cbpi.utils.utils import load_config
from zipfile import ZipFile
from cbpi.craftbeerpi import CraftBeerPi
import os
import shutil
import yaml
import click
from subprocess import call
from importlib_metadata import version, metadata

from jinja2 import Template
class CraftBeerPiCli():
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
        with open('/boot/config.txt', 'w') as f:
            f.write("dtoverlay=w1-gpio,gpiopin=4,pullup=on")
        print("/boot/config.txt created")

    def list_one_wire(self):
        print("List 1Wire")
        call(["modprobe", "w1-gpio"])
        call(["modprobe", "w1-therm"])
        try:
            for dirname in os.listdir('/sys/bus/w1/devices'):
                if (dirname.startswith("28") or dirname.startswith("10")):
                    print(dirname)
        except Exception as e:
            print(e)

    def plugins_list(self):
        print("--------------------------------------")
        print("List of active plugins")
        try:
            with open(self.config.get_file_path("config.yaml"), 'rt') as f:
                data = yaml.load(f, Loader=yaml.FullLoader)

                for p in data["plugins"]:
                    try:
                        p_metadata= metadata(p)
                        p_Homepage= p_metadata['Home-page']
                        p_version = p_metadata['Version']
                        p_Author = p_metadata['Author']
                        print("- ({})\t{}".format(p_version,p))
                    except Exception as e:
                        print (e)
                        pass
        except Exception as e:
            print(e)
            pass
        print("--------------------------------------")

    def plugins_add(configFolder, package_name):
        if package_name is None:
            print("Pleaes provide a plugin Name")
            return

        if package_name == 'autostart':
            print("Add craftbeerpi.service to systemd")
            try:
                if os.path.exists(os.path.join("/etc/systemd/system","craftbeerpi.service")) is False:
                    srcfile = os.path.join(configFolder.get_file_path("craftbeerpi.service"))
                    destfile = os.path.join("/etc/systemd/system")
                    shutil.copy(srcfile, destfile)
                    print("Copied craftbeerpi.service to /etc/systemd/system")
                    os.system('systemctl enable craftbeerpi.service')
                    print('Enabled craftbeerpi service')
                    os.system('systemctl start craftbeerpi.service')
                    print('Started craftbeerpi.service')
                else:
                    print("craftbeerpi.service is already located in /etc/systemd/system")
            except Exception as e:
                print(e)
                return
            return

        if package_name == 'chromium':
            print("Add chromium.desktop to /etc/xdg/autostart/")
            try:
                if os.path.exists(os.path.join("/etc/xdg/autostart/","chromium.desktop")) is False:
                    srcfile = configFolder.get_file_path("chromium.desktop")
                    destfile = os.path.join("/etc/xdg/autostart/")
                    shutil.copy(srcfile, destfile)
                    print("Copied chromium.desktop to /etc/xdg/autostart/")
                else:
                    print("chromium.desktop is already located in /etc/xdg/autostart/")
            except Exception as e:
                print(e)
                return
            return

        installation = True
        try:
            try:
                p_metadata= metadata(package_name)
                p_name=p_metadata['Name']
                #if p_name != package_name:
                #    print("Error. Package name {} does not exist. Did you mean {}".format(package_name,p_name))
                #    installation = False
            except Exception as e:
                print("Error. Package {} cannot be found in installed packages".format(package_name))
                installation = False
            if installation:
                with open(configFolder.get_file_path("config.yaml"), 'rt') as f:
                    data = yaml.load(f, Loader=yaml.FullLoader)
                    if package_name in data["plugins"]:
                        print("")
                        print("Plugin {} already active".format(package_name))
                        print("")
                        return
                    data["plugins"].append(package_name)
                with open(configFolder.get_file_path("config.yaml"), 'w') as outfile:
                    yaml.dump(data, outfile, default_flow_style=False)
                print("")
                print("Plugin {} activated".format(package_name))
                print("")
        except Exception as e:
            print(e)
            pass

    def plugin_remove(package_name, configFolder):
        if package_name is None:
            print("Pleaes provide a plugin Name")
            return

        if package_name == 'autostart':
            print("Remove craftbeerpi.service from systemd")
            try:
                status = os.popen('systemctl list-units --type=service --state=running | grep craftbeerpi.service').read()
                if status.find("craftbeerpi.service") != -1:
                    os.system('systemctl stop craftbeerpi.service')
                    print('Stopped craftbeerpi service')
                    os.system('systemctl disable craftbeerpi.service')
                    print('Removed craftbeerpi.service as service')
                else:
                    print('craftbeerpi.service service is not running')

                if os.path.exists(os.path.join("/etc/systemd/system","craftbeerpi.service")) is True:
                    os.remove(os.path.join("/etc/systemd/system","craftbeerpi.service")) 
                    print("Deleted craftbeerpi.service from /etc/systemd/system")
                else:
                    print("craftbeerpi.service is not located in /etc/systemd/system")
            except Exception as e:
                print(e)
                return
            return

        if package_name == 'chromium':
            print("Remove chromium.desktop from /etc/xdg/autostart/")
            try:
                if os.path.exists(os.path.join("/etc/xdg/autostart/","chromium.desktop")) is True:
                    os.remove(os.path.join("/etc/xdg/autostart/","chromium.desktop"))
                    print("Deleted chromium.desktop from /etc/xdg/autostart/")
                else:
                    print("chromium.desktop is not located in /etc/xdg/autostart/")
            except Exception as e:
                print(e)
                return
            return


        try:
            with open(configFolder.get_file_path("config.yaml"), 'rt') as f:
                data = yaml.load(f, Loader=yaml.FullLoader)

                data["plugins"] = list(filter(lambda k: package_name not in k, data["plugins"]))
                with open(configFolder.get_file_path("config.yaml"), 'w') as outfile:
                    yaml.dump(data, outfile, default_flow_style=False)
            print("")
            print("Plugin {} deactivated".format(package_name))
            print("")
        except Exception as e:
            print(e)
            pass

    def plugin_create(name):
        if os.path.exists(os.path.join(".", name)) is True:
            print("Cant create Plugin. Folder {} already exists ".format(name))
            return

        url = 'https://github.com/Manuel83/craftbeerpi4-plugin-template/archive/main.zip'
        r = requests.get(url)
        with open('temp.zip', 'wb') as f:
            f.write(r.content)

        with ZipFile('temp.zip', 'r') as repo_zip:
            repo_zip.extractall()

        os.rename("./craftbeerpi4-plugin-template-main", os.path.join(".", name))
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
        template = templateEnv.get_template(TEMPLATE_FILE)
        outputText = template.render(name=name)

        with open(os.path.join(".", name, name, "config.yaml"), "w") as fh:
            fh.write(outputText)
        print("")
        print("")
        print(
            "Plugin {} created! See https://openbrewing.gitbook.io/craftbeerpi4_support/readme/development how to run your plugin ".format(
                name))
        print("")
        print("Happy Development! Cheers")
        print("")
        print("")


@click.group()
@click.pass_context
@click.option('--config-folder-path', '-c', default="./config", type=click.Path(), help="Specify where the config folder is located. Defaults to './config'.")
def main(context, config_folder_path):
    level = logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    cbpi_cli = CraftBeerPiCli(ConfigFolder(config_folder_path))
    context.obj = cbpi_cli
    pass

@main.command()
@click.pass_context
def setup(context):
    '''Create Config folder'''
    context.obj.setup()

@main.command()
@click.pass_context
@click.option('--list', is_flag=True, help="List all 1Wire Devices")
@click.option('--setup', is_flag=True, help="Setup 1Wire on Raspberry Pi")
def onewire(context, list, setup):
    '''Setup 1wire on Raspberry Pi'''
    if setup is True:
        context.obj.setup_one_wire()
    if list is True:
        context.obj.list_one_wire()

@main.command()
@click.pass_context
def start(context):
    context.obj.start()

@main.command()
@click.pass_context
def plugins(context):
    '''List active plugins'''
    context.obj.plugins_list()

@main.command()
@click.argument('name')
@click.pass_context
def add(context, name):
    '''Activate Plugin, autostart or chromium '''
    context.obj.plugins_add(name)

@main.command()
@click.pass_context
@click.argument('name')
def remove(context, name):
    '''Deactivate Plugin, autostart or chromium'''
    context.obj.plugin_remove(name)

@main.command()
@click.pass_context
@click.argument('name')
def create(context, name):
    '''Create New Plugin'''
    context.obj.plugin_create(name)