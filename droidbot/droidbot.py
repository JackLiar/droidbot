# This file contains the main class of droidbot
# It can be used after AVD was started, app was installed, and adb had been set up properly
# By configuring and creating a droidbot instance,
# droidbot will start interacting with Android in AVD like a human
import logging
import os
import shutil
import sys
import xmlrpc.client
from os import PathLike
from threading import Timer
from typing import Optional, Union

import pkg_resources

from .app import App
from .device import Device
from .env_manager import AppEnvManager, EnvPolicy
from .input_manager import DEFAULT_EVENT_COUNT, DEFAULT_EVENT_INTERVAL, InputManager
from .input_policy import InputPolicyName


class DroidBot(object):
    """
    The main class of droidbot
    """

    # this is a single instance class
    instance = None

    def __init__(
        self,
        app_path: PathLike,
        device_serial: str,
        is_emulator=False,
        output_dir: PathLike = None,
        env_policy: EnvPolicy = EnvPolicy.default(),
        policy_name: InputPolicyName = InputPolicyName.default(),
        random_input=False,
        script_path: Optional[PathLike] = None,
        event_count: int = DEFAULT_EVENT_COUNT,
        event_interval: float = DEFAULT_EVENT_INTERVAL,
        timeout: float = 0.0,
        keep_app=False,
        keep_env=False,
        cv_mode=False,
        debug_mode=False,
        profiling_method: Union[str, int] = None,
        grant_perm=False,
        enable_accessibility_hard=False,
        master: Optional[str] = None,
        humanoid: Optional[str] = None,
        ignore_ad=False,
        replay_output: Optional[PathLike]=None,
    ):
        """
        initiate droidbot with configurations
        :return:
        """
        self.logger = logging.getLogger("DroidBot")
        self.logger.level =logging.DEBUG if debug_mode else logging.INFO 
        DroidBot.instance = self

        self.output_dir = output_dir
        if output_dir is not None:
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
            html_index_path = pkg_resources.resource_filename("droidbot", "resources/index.html")
            stylesheets_path = pkg_resources.resource_filename("droidbot", "resources/stylesheets")
            target_stylesheets_dir = os.path.join(output_dir, "stylesheets")
            if os.path.exists(target_stylesheets_dir):
                shutil.rmtree(target_stylesheets_dir)
            shutil.copy(html_index_path, output_dir)
            shutil.copytree(stylesheets_path, target_stylesheets_dir)

        self.timeout = timeout
        self.timer = None
        self.keep_env = keep_env
        self.keep_app = keep_app

        self.device = None
        self.app = None
        self.droidbox = None
        self.env_manager = None
        self.input_manager = None
        self.enable_accessibility_hard = enable_accessibility_hard
        self.humanoid = humanoid
        self.ignore_ad = ignore_ad
        self.replay_output = replay_output

        self.enabled = True

        self.device = Device(
            device_serial=device_serial,
            is_emulator=is_emulator,
            output_dir=self.output_dir,
            cv_mode=cv_mode,
            grant_perm=grant_perm,
            enable_accessibility_hard=self.enable_accessibility_hard,
            humanoid=self.humanoid,
            ignore_ad=ignore_ad,
        )
        self.app = App(app_path, output_dir=self.output_dir)

        self.env_manager = AppEnvManager(device=self.device, app=self.app, env_policy=env_policy)
        self.input_manager = InputManager(
            device=self.device,
            app=self.app,
            policy_name=policy_name,
            random_input=random_input,
            event_count=event_count,
            event_interval=event_interval,
            script_path=script_path,
            profiling_method=profiling_method,
            master=master,
            replay_output=replay_output,
        )

    @staticmethod
    def get_instance():
        if DroidBot.instance is None:
            logging.error("Error: DroidBot is not initiated!")
            sys.exit(-1)
        return DroidBot.instance

    def start(self):
        """
        start interacting
        :return:
        """
        if not self.enabled:
            return
        self.logger.info("Starting DroidBot")
        try:
            if self.timeout > 0:
                self.timer = Timer(self.timeout, self.stop)
                self.timer.start()

            self.device.set_up()

            if not self.enabled:
                return
            self.device.connect()

            if not self.enabled:
                return
            self.device.install_app(self.app)

            if not self.enabled:
                return
            self.env_manager.deploy()

            if not self.enabled:
                return
            if self.droidbox is not None:
                self.droidbox.set_apk(self.app.app_path)
                self.droidbox.start_unblocked()
                self.input_manager.start()
                self.droidbox.stop()
                self.droidbox.get_output()
            else:
                self.input_manager.start()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt.")
            pass
        except Exception as e:
            self.logger.exception(e)
            self.stop()
            sys.exit(-1)

        self.stop()
        self.logger.info("DroidBot Stopped")

    def stop(self):
        self.enabled = False
        if self.timer and self.timer.is_alive():
            self.timer.cancel()
        if self.env_manager:
            self.env_manager.stop()
        if self.input_manager:
            self.input_manager.stop()
        if self.droidbox:
            self.droidbox.stop()
        if self.device:
            self.device.disconnect()
            if not self.keep_env:
                self.device.tear_down()
            if not self.keep_app:
                self.device.uninstall_app(self.app)
        if hasattr(self.input_manager.policy, "master") and self.input_manager.policy.master:
            proxy = xmlrpc.client.ServerProxy(self.input_manager.policy.master)
            if self.device:
                proxy.stop_worker(self.device.serial)


class DroidBotException(Exception):
    pass
