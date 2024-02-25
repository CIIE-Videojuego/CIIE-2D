from scipy.interpolate import CubicSpline
from typing_extensions import deprecated

from game.map.grid import Grid
from utils.algorithms import *
from utils.auxiliar import *
from utils.constants import *


# ====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====#
#                                        ENEMY CLASS                                            #
# ====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====*====#

class Enemy(pygame.sprite.Sprite):
    def __init__(self, pos, movement_speed, rotation_speed, grid: Grid, window, areas):
        """
            Initializes the Enemy sprite.

            Args:
                pos (tuple): The initial position (x, y) of the sprite.
                movement_speed (float): The movement speed of the sprite.
                rotation_speed (float): The rotation speed of the sprite.
                grid (Grid): The grid object for pathfinding.
                window (pygame.Surface): The game window surface.

            Returns:
                None
            """
        super().__init__()
        self.groups = []

        # 1. ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #    ~~ VISUAL REPRESENTATION ~~
        #    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.x, self.y = pos
        self.size = NPC_SIZE
        self.offset = VIEW_OFFSET * (NPC_SIZE / 20)
        self.image = pygame.Surface((NPC_SIZE, NPC_SIZE))
        self.image.fill((0, 0, 0))
        self.rect = self.image.get_rect()
        self.rect.center = (self.x, self.y)

        # 2. ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #    ~~ MOVEMENT AND ROTATION ~~
        #    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.angle = NPC_ANGLE
        self.speed = movement_speed
        self.rotation = rotation_speed
        self.setting_rotation = True
        self.setting_path = False
        self.delta_x = -math.cos(math.radians(self.angle)) * self.offset
        self.delta_y = math.sin(math.radians(self.angle)) * self.offset
        self.areas = areas

        # 3. ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #    ~~ PATHFINDING ALGORITHM ~~
        #    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.grid = grid
        self.end_node = None
        self.start_node = None
        self.path_nodes = []
        self.path_points = []
        self.next_point = None

        # 4. ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #    ~~ RAY CASTING AND VISION ~~
        #    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.ray_cone = FIELD_OF_VISION
        self.ray_reach = REACH_OF_VISION
        self.corners = []
        self.mask = None # Deprecated parameter
        self.win_height = window.get_height()
        self.win_width = window.get_width()

    def draw(self, surface, offset):
        ##############################
        # DRAWING RECTANGLE
        ##############################
        rect_surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.rect(rect_surface, GREEN, (0, 0, self.size, self.size))
        rotated_rect = pygame.transform.rotate(rect_surface, self.angle)
        rect = rotated_rect.get_rect()
        rect.center = (self.x, self.y)
        surface.blit(rotated_rect, (rect.x - offset.x, rect.y - offset.y))

        ##############################
        # DRAWING TRIANGLE
        ##############################
        end_point = (self.x - self.delta_x * 10 - offset.x, self.y - self.delta_y * 10 - offset.y)
        angle_to_horizontal = math.atan2(self.delta_y, self.delta_x)
        triangle_size = self.size // 2
        triangle_points = [
            end_point,
            (
                end_point[0] + triangle_size * math.cos(angle_to_horizontal - math.radians(30)),
                end_point[1] + triangle_size * math.sin(angle_to_horizontal - math.radians(30)),
            ),
            (
                end_point[0] + triangle_size * math.cos(angle_to_horizontal + math.radians(30)),
                end_point[1] + triangle_size * math.sin(angle_to_horizontal + math.radians(30)),
            ),
        ]
        pygame.draw.polygon(surface, (255, 0, 0), triangle_points)
        # nodes = list(map(lambda node: node.get_pos(), self.path_nodes))
        # self.draw_path(surface, nodes, offset)

    def update(self):
        ##############################
        # PATHFINDING AND ROTATION
        ##############################
        current_pos = (self.x, self.y)
        if self.next_point is None or self.end_node.compare_pos(current_pos):
            self.pathfinding()
            self.setting_path = True
            self.setting_rotation = True
        elif self.has_reached(self.next_point):
            self.set_next_point()

        #################################
        # DRAWING PATH (OPTIONAL)
        #################################
        # if len(self.points_from_path()) > 1 and show:  self.draw_path(self.path_points, 1, (0, 0, 255))

        ##############################
        # UPDATING ANGLE AND MOVEMENT
        ##############################
        end_point = self.next_point
        updated_angle = self.angle_to_point(end_point)

        if self.setting_path:
            if self.is_facing(end_point):
                self.setting_path = False
            else:
                if self.setting_rotation:
                    if self.shortest_rotation(end_point) > 0:
                        self.rotation = abs(self.rotation)
                    else:
                        self.rotation = -1 * abs(self.rotation)
                    self.setting_rotation = False
                self.rotate(self.rotation)
                self.delta_x = -math.cos(math.radians(self.angle)) * self.offset
                self.delta_y = math.sin(math.radians(self.angle)) * self.offset
        else:
            if abs(updated_angle - self.angle) > 45:
                self.set_next_point()
                end_point = self.next_point
                updated_angle = self.angle_to_point(end_point)

            self.angle = updated_angle

            self.delta_x = -math.cos(math.radians(self.angle)) * self.offset
            self.delta_y = math.sin(math.radians(self.angle)) * self.offset

            self.x -= self.delta_x * self.speed
            self.y -= self.delta_y * self.speed

        ##############################
        # CASTING RAYS
        ##############################
        self.cast()

        # Update sprite
        self.rect.center = (self.x, self.y)

    def kill(self):
        for group in self.groups:
            group.remove(self)
        del self

    def add(self, *groups):
        for group in groups:
            group.add(self)
            if group not in self.groups:
                self.groups.append(group)

    def remove(self, *groups):
        for group in groups:
            group.remove(self)
            if group in self.groups:
                self.groups.remove(group)

    # ####################################################################### #
    #                               PATHFINDING                               #
    # ####################################################################### #

    def pathfinding(self):
        self.set_start()
        self.set_random_end()
        self.path_nodes = a_star(self)
        self.path_points = self.interpolate_points(8)
        self.next_point = self.path_points[1]
        self.path_nodes.pop(0)
        self.path_points.pop(0)

    def set_start(self):
        self.start_node = self.grid.get_node((self.x, self.y))

    def set_manual_end(self, node):
        self.end_node = node

    def set_random_end(self):
        self.end_node = self.grid.get_random_node_from_zones(self.areas)

    def set_next_point(self):
        try:
            index = self.path_points.index(self.next_point)
            self.next_point = self.path_points[index + 1]
            self.path_points.pop(index)
        except Exception as e:
            print(e)

    def has_reached(self, point, threshold: int = 1):
        return (point[0] - threshold <= self.x <= point[0] + threshold) and (
                point[1] - threshold <= self.y <= point[1] + threshold)

    def points_from_path(self):
        points = []
        for square in self.path_nodes:
            points.append(square.get_pos())
        return points

    def interpolate_points(self, segments):
        points = np.array(self.points_from_path())
        t = np.arange(len(points))
        x = points[:, 0]
        y = points[:, 1]

        cs_x = CubicSpline(t, x)
        cs_y = CubicSpline(t, y)

        smooth_points = []
        for i in range(len(points) - 1):
            smooth_t = np.linspace(i, i + 1, segments)
            smooth_points.extend(np.column_stack([cs_x(smooth_t), cs_y(smooth_t)]))

        smooth_points.append(points[-1])

        return [tuple(point) for point in smooth_points]

    # ####################################################################### #
    #                               RAY CASTING                               #
    # ####################################################################### #

    def cast(self):
        ##############################
        # INITIALIZE VARIABLES
        ##############################
        start = increase_degree(self.angle, self.ray_cone / 2 + 1)
        ray_degree = start
        end = increase_degree(self.angle, -self.ray_cone / 2)
        previous_point = None
        corner_list = []
        contact_point = None

        ##############################
        # CASTING RAYS
        ##############################
        while compare_degree(ray_degree, start, end):
            ray_degree = increase_degree(ray_degree, -1)
            tan_ray_angle = math.tan(math.radians(ray_degree))

            ##############################
            # HORIZONTAL RAYS
            ##############################
            ray_distance = 0
            if ray_degree == 90 or ray_degree == 270:
                ray_degree += 0.001
            if ray_degree > 180:
                up = False
                ray_y = math.ceil(self.y / self.grid.gap) * self.grid.gap + 0.001
                offset_y = -self.grid.gap
            else:
                up = True
                ray_y = math.ceil(self.y / self.grid.gap) * self.grid.gap - self.grid.gap
                offset_y = self.grid.gap
            ray_x = (self.y - ray_y) / tan_ray_angle + self.x if tan_ray_angle != 0 else self.x
            offset_x = offset_y / tan_ray_angle if tan_ray_angle != 0 else 0
            while ray_distance < self.ray_reach and ray_distance < self.grid.size:
                map_x = int(ray_x // self.grid.gap)
                map_y = int(ray_y // self.grid.gap - (1 if up else 0))
                if 0 <= map_x < self.grid.size and 0 <= map_y < self.grid.size and self.grid.nodes[map_x][
                    map_y].is_barrier():
                    ray_distance = self.ray_reach
                else:
                    ray_x = ray_x + offset_x
                    ray_y = ray_y - offset_y
                    ray_distance += 1
            horizontal_x, horizontal_y = ray_x, ray_y
            horizontal_distance = dist(self.x, self.y, horizontal_x, horizontal_y)

            ##############################
            # VERTICAL RAYS
            ##############################
            ray_distance = 0
            if ray_degree == 90 or ray_degree == 270:
                ray_degree += 0.001
            if 90 < ray_degree < 270:
                right = False
                ray_x = math.ceil(self.x / self.grid.gap) * self.grid.gap - self.grid.gap
                offset_x = -self.grid.gap
            else:
                right = True
                ray_x = math.ceil(self.x / self.grid.gap) * self.grid.gap + 0.001
                offset_x = self.grid.gap
            ray_y = (self.x - ray_x) * tan_ray_angle + self.y if tan_ray_angle != 0 else self.y
            offset_y = offset_x * tan_ray_angle if tan_ray_angle != 0 else 0
            while ray_distance < self.ray_reach and ray_distance < self.grid.size:
                map_x = int(ray_x // self.grid.gap - (0 if right else 1))
                map_y = int(ray_y // self.grid.gap)
                if 0 <= map_x < self.grid.size and 0 <= map_y < self.grid.size and self.grid.nodes[map_x][
                    map_y].is_barrier():
                    ray_distance = self.ray_reach
                else:
                    ray_x += offset_x
                    ray_y -= offset_y
                    ray_distance += 1
            vertical_x, vertical_y = ray_x, ray_y
            vertical_distance = dist(self.x, self.y, vertical_x, vertical_y)

            ##############################
            # COMPARING AND UPDATING CONTACT POINTS
            ##############################
            if vertical_distance < horizontal_distance:
                contact_point = (vertical_x, vertical_y)
            else:
                contact_point = (horizontal_x, horizontal_y)
            if not is_point_neighbour(previous_point, contact_point):
                if previous_point is None:
                    corner_list.append(((self.x, self.y), contact_point))
                else:
                    corner_list.append((previous_point, contact_point))
            previous_point = contact_point

        ##############################
        # FINALIZING CORNER LIST AND UPDATING MASK
        ##############################
        corner_list.append((contact_point, (self.x, self.y)))
        self.corners = corner_list

    # ####################################################################### #
    #                                 ROTATION                                #
    # ####################################################################### #

    def angle_to_point(self, point, show=False):
        """
                    Calculates the angle between the sprite and a given point.

                    Args:
                        point (tuple): The target point (x, y).
                        show (bool, optional): Flag to display angle calculations. Defaults to False.

                    Returns:
                        float: The angle in degrees between the sprite and the point.
                    """
        delta_x = point[0] - self.x
        delta_y = point[1] - self.y
        angle_rad = math.atan2(delta_y, delta_x)
        angle_deg = math.degrees(angle_rad)
        if show:
            print('Original: ' + str(angle_deg))
        if angle_deg < 0:
            angle_final = -angle_deg
        else:
            angle_final = 360 - angle_deg
        if show:
            print('Transformed: ' + str(angle_final), '\n')
        return angle_final

    def is_facing(self, point):
        """
                    Checks if the sprite is facing a given point within a certain threshold angle.

                    Args:
                        point (tuple): The target point (x, y).

                    Returns:
                        bool: True if facing the point within threshold angle, False otherwise.
                    """
        threshold_angle = abs(self.rotation) + 1
        angle_to_point_deg = self.angle_to_point(point)
        angle_diff = (angle_to_point_deg - self.angle + 180) % 360 - 180
        return abs(angle_diff) <= threshold_angle

    def shortest_rotation(self, point):
        """
                    Determines the shortest rotation direction towards a given point.

                    Args:
                        point (tuple): The target point (x, y).

                    Returns:
                        int: 1 if clockwise rotation, -1 if counterclockwise rotation.
                    """
        target_angle = self.angle_to_point(point)
        diff = (target_angle - self.angle + 360) % 360
        return 1 if diff <= 180 else -1

    def rotate(self, rotation):
        self.angle = (self.angle + rotation) % 360

    # ####################################################################### #
    #                                DEPRECATED                               #
    # ####################################################################### #

    @deprecated("This method is too expensive.")
    def update_mask(self, corners):
        ##############################
        # COLLECT VERTICES
        ##############################
        vertices = []
        for pair in corners:
            point1, point2 = pair
            vertices.append(point1)
            vertices.append(point2)

        ##############################
        # CREATE MASK SURFACE
        ##############################
        mask_surface = pygame.Surface((self.win_width, self.win_height), pygame.SRCALPHA)

        ##############################
        # CREATE LIMIT CIRCLE MASK
        ##############################
        pygame.draw.circle(mask_surface, (255, 255, 255, 255), (int(self.x), int(self.y)),
                           REACH_OF_VISION * SQUARE_SIZE)
        limit_circle_mask = pygame.mask.from_surface(mask_surface)

        ##############################
        # CREATE MASK
        ##############################
        mask_surface.fill((0, 0, 0, 0))
        if len(vertices) > 2:
            pygame.draw.polygon(mask_surface, (255, 255, 255), vertices)
        pygame.draw.circle(mask_surface, (255, 255, 255, 255), (int(self.x), int(self.y)), self.size * 3)
        self.mask = pygame.mask.from_surface(mask_surface)
        self.mask = self.mask.overlap_mask(limit_circle_mask, (0, 0))

    @deprecated("This method is too expensive.")
    def draw_mask(self, surface):
        mask_surface = pygame.Surface((surface.get_height(), surface.get_height()), pygame.SRCALPHA)

        fill_mask(mask_surface, self.mask)
        surface.blit(mask_surface, (0, 0))

    @deprecated("This method is a debugging tool.")
    def draw_circle_and_line(self, surface, pos, origin_pos=None):
        if origin_pos is None:
            pygame.draw.line(surface, (0, 255, 0), (self.x, self.y), pos, 1)
            pygame.draw.circle(surface, (255, 0, 0), pos, 3)
        else:
            pygame.draw.line(surface, (0, 255, 0), origin_pos, pos, 1)
            pygame.draw.circle(surface, (255, 0, 0), pos, 3)

    @deprecated("This method is deprecated.")
    def draw_point_of_view(self, surface, corners):
        vertices = []
        for pair in corners:
            point1, point2 = pair
            vertices.append(point1)
            vertices.append(point2)
        pygame.draw.polygon(surface, PASTEL_RED, vertices)

    @deprecated("This method is a debugging tool.")
    def draw_path(self, surface, point_list, offset, point_size=1, point_color=(255, 0, 0)):
        for point in point_list:
            pygame.draw.circle(surface, point_color, point-offset, point_size)
