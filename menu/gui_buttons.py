from menu.prototypes.gui_prototypes import Button, ButtonSwitch
from utils.enums import Controls as Ctl
from utils.filepaths import *

import pygame


class ButtonPlay(Button):
    def __init__(self, screen):
        Button.__init__(self, screen, BUTTON_PLAY, (500, 50))

    def activate(self):
        self.screen.menu.run()


class ButtonConfiguration(Button):
    def __init__(self, screen):
        Button.__init__(self, screen, BUTTON_CONFIGURATION, (500, 90))

    def activate(self):
        self.screen.menu.show_configuration_screen()


class ButtonCredits(Button):
    def __init__(self, screen):
        Button.__init__(self, screen, BUTTON_CREDITS, (500, 130))

    def activate(self):
        self.screen.menu.show_credits_screen()


class ButtonExit(Button):
    def __init__(self, screen):
        Button.__init__(self, screen, BUTTON_EXIT, (500, 170))

    def activate(self):
        self.screen.menu.exit()


class ButtonBackToMenu(Button):
    def __init__(self, screen):
        Button.__init__(self, screen, BUTTON_BACK, (520, 200))

    def activate(self):
        self.screen.menu.show_starting_screen()


class SwitchVolume(ButtonSwitch):
    def __init__(self, screen):
        ButtonSwitch.__init__(self, screen, SWITCH_OFF, SWITCH_ON, (500, 90), "On")

    def activate(self):
        # Cambiar el estado del interruptor
        if self.state == 'Off':
            pygame.mixer.music.set_volume(1.0)  # Max volume
            self.state = 'On'
            self.image = self.image_2
        else:
            pygame.mixer.music.set_volume(0.0)  # Mute
            self.state = 'Off'
            self.image = self.image_1


class SwitchController(ButtonSwitch):
    def __init__(self, screen):
        ButtonSwitch.__init__(self, screen, BUTTON_ARROWS, BUTTON_WASD, (500, 130), "WASD")

    def activate(self):
        # Cambiar el estado del interruptor
        if self.state == 'Arrows':
            self.screen.menu.set_movement_option(Ctl.WASD)
            self.state = 'WASD'
            self.image = self.image_2
        else:
            self.screen.menu.set_movement_option(Ctl.Arrows)
            self.state = 'Arrows'
            self.image = self.image_1

class SwitchLanguage(ButtonSwitch):
    def __init__(self, screen):
        ButtonSwitch.__init__(self, screen, SPAIN, UNITED_KINGDOM, (500, 170), "en")

    def activate(self):
        # Cambiar el estado del interruptor
        if self.state == 'es':
            self.screen.menu.set_language('en')
            self.state = 'en'
            self.image = self.image_2
        else:
            self.screen.menu.set_language('es')
            self.state = 'es'
            self.image = self.image_1
