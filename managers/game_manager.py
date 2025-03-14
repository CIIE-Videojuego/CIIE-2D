import json

import pygame
from pygamepopup.components import InfoBox, Button
from pygamepopup.constants import BUTTON_SIZE
from pygamepopup.menu_manager import MenuManager
from typing_extensions import deprecated

from game.entities.enemy import Enemy
from game.entities.player import Player
from game.groups.enemies_group import Enemies
from game.groups.interface_group import Interface
from game.groups.render_group import Camera
from game.map.grid import Grid
from game.map.level import Level
from game.ui.ui_bar import Bar
from game.ui.ui_keys import Keys
from game.ui.ui_level import Indicator
from game.ui.ui_text import Message
from managers.prototypes.scene_prototype import Scene
from utils.constants import *
from utils.i18n import get_translation
from utils.paths.assets_paths import FONT, POPUP_IMAGE_PAUSE, POPUP_IMAGE_DEATH, POPUP_IMAGE_LEVEL, POPUP_IMAGE_FINISHED
from utils.paths.maps_paths import LEVELS


class GameManager(Scene):
    def __init__(self, manager, audio, level_number=1):
        Scene.__init__(self, manager)

        self.win = pygame.display.get_surface()
        self.win_size = self.win.get_width()

        with open(LEVELS[level_number], 'r') as file:
            data = file.read().replace('\n', '')

        self.level = Level(**json.loads(data))

        self.player = None
        self.grid = Grid(
            size=100,
            win=self.win,
            border_map_path=self.level.map.border_map_path,
            tile_map_path=self.level.map.tile_map_path,
            objects_map_path=self.level.map.objects_map_path,
            sprite_sheet_path=self.level.level_sprite_sheet.path,
            ss_columns=self.level.level_sprite_sheet.columns,
            ss_rows=self.level.level_sprite_sheet.rows
        )

        self.end_current_frame = -1
        self._end_delay_frame = 2
        self._end_pass_frame = self._end_delay_frame
        self.end_max_frame = len(DOOR_TILES)

        self.grid.set_spawn_square(self.level.coordinates.player_initial_x, self.level.coordinates.player_initial_y)
        self.enemies = Enemies()
        self.all_sprites = Camera()
        self.interface = Interface()
        self.level_ui = Indicator(self.win)
        self.audio = audio

        self._start()

        for x, y in zip(self.level.coordinates.exit_x, self.level.coordinates.exit_y):
            self.grid.set_exit_square(x, y)

        self.menu_manager = MenuManager(self.win)

        self.pause_menu = None
        self.death_menu = None
        self.finished_level_menu = None
        self.game_finished_menu = None

        self.set_menus()

    def events(self, event_list):
        for event in event_list:
            if event.type == pygame.QUIT:
                self.exit()
            elif self.is_open_menu():
                if event.type == pygame.MOUSEMOTION:
                    self.menu_manager.motion(event.pos)  # Highlight buttons upon hover
                elif event.type == pygame.KEYDOWN and self.menu_manager.active_menu.identifier == PAUSE_MENU_ID:
                    if event.key == pygame.K_ESCAPE:
                        self.menu_manager.close_active_menu()
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 or event.button == 3:
                        self.menu_manager.click(event.button, event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.open_menu(self.pause_menu)

    def set_door(self):
        if self.end_current_frame < 0:
            pair = DOOR_TILES[0]
        else:
            pair = DOOR_TILES[self.end_current_frame]
        count = 0
        for x, y in zip(self.level.coordinates.exit_x, self.level.coordinates.exit_y):
            door = self.grid.get_node_from_array(x, y - 1)
            door.set_tile_set([71, pair[count]])
            count += 1

    def draw(self, screen):
        if self.end_current_frame >= 0:
            if self.end_current_frame >= self.end_max_frame:
                if self.level.level_number == len(LEVELS):
                    self.open_menu(self.game_finished_menu)
                else:
                    self.open_menu(self.finished_level_menu)
            else:
                if self._end_pass_frame <= 0:
                    self.set_door()
                    self.end_current_frame += 1
                    self._end_pass_frame = self._end_delay_frame
                else:
                    self._end_pass_frame = self._end_pass_frame - 1

        self.all_sprites.draw(player=self.player, grid=self.grid)
        self.interface.draw(surface=screen)

        if self.is_open_menu():
            self.menu_manager.display()

        pygame.display.update()

    def update(self, **kwargs):
        if not self.is_open_menu() and self.end_current_frame < 0:
            kwargs['player'] = self.player
            kwargs['player_mask'] = self.all_sprites.return_player_mask(self.player)
            kwargs['enemy_mask'] = self._render()
            kwargs['language'] = self.manager.get_language()
            self.all_sprites.update(**kwargs)
            self.interface.update(**kwargs)

    def notified(self):
        if self.player.detected():
            self.audio.play_detected()
        else:
            self.audio.stop_detected()

        if not self.player.alive():  # Player has died
            self.audio.play_death()
            self.open_menu(self.death_menu)

        if self.player.in_door():  # Player has reached the end
            if self.player.has_key():
                self.audio.stop_movement()
                self.audio.play_finish()
                self._open_doors()
                """if self.level.level_number == len(LEVELS):
                    self.open_menu(self.game_finished_menu)
                else:
                    self.open_menu(self.finished_level_menu)"""
                return

        if self.player.has_key() and self.player.interacted_key():
            self.audio.play_key()

        if self.player.moving():
            self.audio.play_movement()
        else:
            self.audio.stop_movement()

        if self.player.recovering():
            self.audio.play_recovering()
        else:
            self.audio.stop_recovering()

    # ####################################################################### #
    #                               CLASS METHODS                             #
    # ####################################################################### #

    def exit(self):
        self.manager.exit()

    def _close(self):
        self._restart()
        self.audio.music_menu()
        self.manager.change_scene()

    def _advance(self):
        level_number = self.level.level_number

        self._restart()

        if level_number == len(LEVELS):
            # Pantalla ganadora
            print("Congrats! You've finished the game!")  # TODO: cambiar el mensaje a un popup diferente
            self.audio.music_menu()
            self.manager.change_scene()
        else:
            self.manager.advance_level(level_number + 1)

    def _start(self):
        self.key_x, self.key_y = (self.grid.get_random_node_from_zones(self.level.key_zones)).get_grid_pos()
        self.grid.set_key_square(self.key_x, self.key_y)

        self.end_current_frame = -1
        self._end_delay_frame = 2
        self._end_pass_frame = self._end_delay_frame
        self.set_door()

        self._spawn_player()
        self._spawn_enemies()

        self.grid.visible_key = True
        self.set_interface()

    def _resume(self):
        self.close_menu()
        self.player.notify_observers()

    def _restart(self):
        if self.player is not None:
            self._remove_player(self.player)
        self.enemies.remove_all()
        self.close_menu()
        self._start()

    def _open_doors(self):
        self.end_current_frame = 0

    # ####################################################################### #
    #                                  ENTITIES                               #
    # ####################################################################### #

    def _render(self):
        for enemy in self.enemies.sprites():
            vertices = []
            for pair in enemy.corners:
                point1, point2 = pair
                vertices.append(point1)
                vertices.append(point2)
            self.all_sprites.save_enemy_mask(enemy, vertices)

        return self.all_sprites.return_enemy_mask()

    def _add_player(self, player):
        self.player = player
        player.add(self.all_sprites)

    def _remove_player(self, player):
        player.kill()
        self.player = None

    def _spawn_player(self):
        x, y = self.grid.spawn.get_pos()
        player = Player(x, y, SPEED, self.grid)

        self._add_player(player)
        self.enemies.set_player(self.player)
        self.interface.set_player(self.player)

        self.player.add_observer(self)
        self.player.add_observer(self.enemies)
        self.player.add_observer(self.interface)

    def _spawn_enemies(self):
        enemies = self.enemies.spawn(self.grid, self.win, self.level.enemies)
        for enemy in enemies:
            self.enemies.introduce(enemy, self.all_sprites, self.enemies)

    # ####################################################################### #
    #                             MENU METHODS                                #
    # ####################################################################### #

    def is_open_menu(self):
        return self.menu_manager.active_menu is not None

    def open_menu(self, menu_to_open):
        self.audio.pause()
        self.close_menu()
        self.menu_manager.open_menu(menu_to_open)

    def close_menu(self):
        self.menu_manager.close_active_menu()

    def set_menus(self):
        font_size = 24
        font_color = GREY
        pause_menu = InfoBox(
            "",
            [
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'resume'),
                        callback=lambda: self._resume(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'restart'),
                        callback=lambda: self._restart(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'main menu'),
                        callback=lambda: self._close(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
            ],
            width=300,
            has_close_button=False,
            identifier=PAUSE_MENU_ID,
            background_path=POPUP_IMAGE_PAUSE
        )
        die_menu = InfoBox(
            "",
            [
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'restart'),
                        callback=lambda: self._restart(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'main menu'),
                        callback=lambda: self._close(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
            ],
            width=300,
            has_close_button=False,
            identifier=DIE_MENU_ID,
            background_path=POPUP_IMAGE_DEATH
        )
        finished_level_menu = InfoBox(
            "",
            [
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'next level'),
                        callback=lambda: self._advance(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'main menu'),
                        callback=lambda: self._close(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
            ],
            width=300,
            has_close_button=False,
            identifier=LEVEL_MENU_ID,
            background_path=POPUP_IMAGE_LEVEL
        )
        game_finished_menu = InfoBox(
            "",
            [
                [
                    Button(
                        title=get_translation(self.manager.get_language(), 'main menu'),
                        callback=lambda: self._close(),
                        size=(BUTTON_SIZE[0], BUTTON_SIZE[1]),
                        text_hover_color=font_color,
                        font=pygame.font.Font(FONT, font_size),
                        no_background=True
                    )
                ],
            ],
            width=300,
            has_close_button=False,
            identifier=FINISHED_GAME_MENU_ID,
            background_path=POPUP_IMAGE_FINISHED
        )
        self.pause_menu = pause_menu
        self.death_menu = die_menu
        self.finished_level_menu = finished_level_menu
        self.game_finished_menu = game_finished_menu

    def set_interface(self):
        bar = Bar(self.win)
        bar.add(self.interface)

        message = Message(self.win)
        message.add(self.interface)

        self.level_ui.set_text(get_translation(self.manager.get_language(), 'level') + str(self.level.level_number))
        self.level_ui.add(self.interface)

        keys = Keys()
        keys.set_position(bar.rect)
        keys.add(self.interface)

    # ####################################################################### #
    #                                DEPRECATED                               #
    # ####################################################################### #

    @deprecated("This method has been replaced")
    def _force_spawn_enemies(self):
        self._remove_all_enemies()

        # Generar 2 guardias (entidad asociada a varias zonas)
        x, y = self.grid.get_random_node_from_zones([1, 2]).get_pos()
        enemy = Enemy((x, y), 0.5, 1, self.grid, self.win, [1, 2])
        self._add_enemy(enemy)

        x, y = self.grid.get_random_node_from_zones([2, 3]).get_pos()
        enemy = Enemy((x, y), 0.5, 1, self.grid, self.win, [2, 3])
        self._add_enemy(enemy)

        # Generar 1 científico (entidad asociada a una única zona)
        x, y = self.grid.get_random_node_from_zones([3]).get_pos()
        enemy = Enemy((x, y), 0.5, 1, self.grid, self.win, [3])
        self._add_enemy(enemy)

        # Generar 1 explorador (entidad que puede recorrer cualquier zona)
        x, y = self.grid.get_random_node().get_pos()
        enemy = Enemy((x, y), 0.5, 1, self.grid, self.win, [])
        self._add_enemy(enemy)

    @deprecated("This method has been replaced")
    def _add_enemy(self, enemy):
        enemy.add(self.all_sprites, self.enemies)

    @deprecated("This method has been replaced")
    def _remove_enemy(self, enemy=None):
        if enemy:
            enemy.kill()
        else:
            self._remove_all_enemies()

    @deprecated("This method has been replaced")
    def _remove_all_enemies(self):
        for enemy in self.enemies.sprites():
            enemy.kill()
