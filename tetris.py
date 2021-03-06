#!/usr/bin/env python3

import os
import sys
import random
import pygame
from enum import Enum
from typing import List, Tuple, Optional

GAME_WIDTH = 10
GAME_HEIGHT = 20

PIECE_STARTING_WIDTH = 4
PIECE_STARTING_HEIGHT = 2

BOX_DIMENSION = 30
START_LEFT = 30
START_TOP = 30

SCREEN_HEIGHT = 720
SCREEN_WIDTH = 1200

REMOTE_GAME_LEFT_MARGIN = START_LEFT + BOX_DIMENSION * (GAME_WIDTH + 5)

SAVE_PATH = os.path.expanduser("~/.pytris-save")

def quit():
    pygame.display.quit()
    pygame.quit()
    sys.exit()

# TODO: It would be great if this could be a @dataclass but charon.kis.agh.edu.pl has an outdated Python version
class Piece:
    def __init__(self, arrangement, color, can_be_first, long_tetrimono_rotation=False, no_rotation=False, id=0):
        self.arrangement = arrangement
        self.color = color
        self.long_tetrimono_rotation = long_tetrimono_rotation
        self.can_be_first = can_be_first
        self.no_rotation = no_rotation
        self.id = id


PIECES = [
    Piece(arrangement=[[1, 2, 1, 1],
                       [0, 0, 0, 0]],
          color=(0x00, 0xff, 0xff),
          long_tetrimono_rotation=True,
          can_be_first=True,
          id=1),

    Piece(arrangement=[[1, 2, 1, 0],
                       [0, 0, 1, 0]],
          color=(0x30, 0x30, 0xff),
          can_be_first=True,
          id=2),

    Piece(arrangement=[[1, 2, 1, 0],
                       [1, 0, 0, 0]],
          color=(0xff, 0xa5, 0x00),
          can_be_first=True,
          id=3),

    Piece(arrangement=[[1, 1, 0, 0],
                       [1, 2, 0, 0]],
          color=(0xff, 0xff, 0x00),
          no_rotation=True,
          can_be_first=True,
          id=4),

    Piece(arrangement=[[0, 1, 1, 0],
                       [1, 2, 0, 0]],
          color=(0x00, 0xff, 0x00),
          can_be_first=False,
          id=5),

    Piece(arrangement=[[1, 2, 1, 0],
                       [0, 1, 0, 0]],
          color=(0x80, 0x00, 0x80),
          can_be_first=True,
          id=6),

    Piece(arrangement=[[1, 2, 0, 0],
                       [0, 1, 1, 0]],
          color=(0xff, 0x00, 0x00),
          can_be_first=False,
          id=7),
]


class RandomPieceGenerator:
    def __init__(self):
        pieces_that_can_be_first = [piece for piece in PIECES if piece.can_be_first]
        self._next_pieces_buffer = [random.choice(pieces_that_can_be_first)]
        self._fill_buffer_if_needed()

    def _fill_buffer_if_needed(self):
        def shuffle_out_of_place(l: list) -> list:
            lst = l.copy()
            random.shuffle(lst)
            return lst

        if len(self._next_pieces_buffer) > 2:
            return

        for piece in shuffle_out_of_place(PIECES):
            self._next_pieces_buffer.append(piece)

    def next(self) -> Piece:
        self._fill_buffer_if_needed()
        return self._next_pieces_buffer.pop(0)

    def peek(self) -> Piece:
        return self._next_pieces_buffer[0]


class BlotType(Enum):
    EMPTY = 0
    PLACED = 1
    FALLING = 2


class Blot:
    def __init__(self, type: BlotType, piece: Piece = None, is_center_blot=False):
        self._type = type
        self._piece = piece
        self._is_center_blot = is_center_blot
        self.color = piece.color if piece else None

    def is_empty(self) -> bool:
        return self._type == BlotType.EMPTY

    def is_falling(self) -> bool:
        return self._type == BlotType.FALLING

    def is_placed(self) -> bool:
        return self._type == BlotType.PLACED

    def is_center_blot(self) -> bool:
        return self._is_center_blot

    def to_placed_blot(self):  # -> Blot  # (Uncomment if Python 3.7 can be used)
        return Blot(BlotType.PLACED, piece=self._piece)

    def should_rotate(self) -> bool:
        return self._piece is not None and not self._piece.no_rotation

    def get_color_id(self):
        if self.is_empty():
            return 0
        elif self.is_placed():
            return self._piece.id
        elif self.is_falling():
            return self._piece.id | 0b1000


class GameOverException(Exception):
    pass


class Game:
    def __init__(self, screen, font, width, start_left=START_LEFT):
        self.screen = screen
        self.random_piece_generator = RandomPieceGenerator()
        self.level = 0
        self.points = 0
        self.frame = 0
        self.lines = 0
        self.pause_font = None
        self.paused = False
        self.font = font
        self.board: List[List[Blot]] = []
        self.running_elision_animation = False
        self.elision_animation_generator = None
        self.start_left = start_left
        self.width = width
        for _ in range(GAME_HEIGHT):
            self.board.append([Blot(BlotType.EMPTY)] * GAME_WIDTH)

    def frames_per_gridcell(self) -> int:
        level_to_frames = {
            0:	36,
            1:	32,
            2:	29,
            3:	25,
            4:	22,
            5:	18,
            6:	15,
            7:	11,
            8:	7,
            9:	5,
            10: 4,
            11: 4,
            12:	4,
            13: 3,
            14: 3,
            15:	3,
            16: 2,
            17: 2,
            18:	2,
        }
        if self.level > 18:
            return 1
        return level_to_frames[self.level]

    def display_pause(self):
        if self.pause_font is None:
            self.pause_font = pygame.font.SysFont('monospace', 100)
        text = self.pause_font.render("Pause", True, (160, 160, 160))
        text_rect = text.get_rect(center=(SCREEN_WIDTH/2, SCREEN_HEIGHT/2))
        self.screen.blit(text, text_rect)
        self.update_screen()

    def display_text(self):
        for row in self.board:
            for piece in row:
                print('-' if piece.is_empty() else 'x', end='')
            print()

    def draw_blot(self, blot: Blot, row=0, column=0, start_dimensions=None, color=None):
        if start_dimensions is None:
            start_dimensions = (self.start_left, START_TOP)

        if not blot.is_empty():
            left = start_dimensions[0] + column * BOX_DIMENSION
            top = start_dimensions[1] + row * BOX_DIMENSION

            border = BOX_DIMENSION * 0.1
            color_scale = 0.8

            blot_color = color or blot.color

            # The border color
            darkened_color = (blot_color[0] * color_scale, blot_color[1] * color_scale, blot_color[2] * color_scale)

            # Draw a blot border
            pygame.draw.rect(self.screen, darkened_color, (left, top, BOX_DIMENSION, BOX_DIMENSION))

            # Draw the inner piece of the blot, covering the border
            pygame.draw.rect(self.screen, blot_color,
                             (left + border, top + border, BOX_DIMENSION - 2 * border, BOX_DIMENSION - 2 * border))

    def clear_display(self):
        # # Clear the whole screen
        pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        # Black game background
        height = BOX_DIMENSION * GAME_HEIGHT
        width = BOX_DIMENSION * GAME_WIDTH
        pygame.draw.rect(self.screen, (0, 0, 0), (self.start_left, START_TOP, width, height))

    def display_next_piece(self):
        top = START_TOP * 3
        left = self.start_left * 4 + (BOX_DIMENSION * GAME_WIDTH)

        # The 'Next piece' box
        pygame.draw.rect(self.screen, (70, 70, 70), (left, top, BOX_DIMENSION * 6, BOX_DIMENSION * 4))

        # The next piece itself
        next_piece = self.random_piece_generator.peek()

        # TODO: this logic should be in the Piece class, for when it gets done instead of the dicts in PIECES
        piece_width = 0
        for row in next_piece.arrangement:
            for col_idx, presence in enumerate(row):
                if presence:
                    piece_width = max(piece_width, col_idx + 1)

        # TODO: well, this.. but properly
        piece_height = 1 if next_piece.long_tetrimono_rotation else 2

        tetrimono_corner_left = left + BOX_DIMENSION + ((BOX_DIMENSION / 2) * (4 - piece_width))
        tetrimono_corner_top = top + BOX_DIMENSION + ((BOX_DIMENSION / 2) * (2 - piece_height))

        for row_idx, row in enumerate(next_piece.arrangement):
            for col_idx, presence in enumerate(row):
                if not presence:
                    continue
                self.draw_blot(Blot(BlotType.FALLING, next_piece),
                               row=row_idx,
                               column=col_idx,
                               start_dimensions=(tetrimono_corner_left, tetrimono_corner_top))

    def shadow_location(self) -> List[Tuple[int, int, Blot]]:
        if not self.has_falling_tetrimono():
            return []

        # Simulate a full fall, grab the fallen blocks coordinates, then back the board to its original state
        board = self.board_copy()

        while self.has_falling_tetrimono():
            falling = [(row, col, blot) for row, col, blot in self.all_blots if blot.is_falling()]
            self.do_fall()

        self.board = board

        return falling

    def display_shadow(self):
        for row, col, blot in self.shadow_location():
            self.draw_blot(blot, row, col, color=(40, 40, 40))

    def display_score(self):
        s1 = "Score: %s" % self.points
        s2 = "Level: %s" % self.level
        text1=self.font.render(s1, 1, (127, 127, 127))
        text2=self.font.render(s2, 1, (127, 127, 127))
        self.screen.blit(text1, (self.start_left * 4 + BOX_DIMENSION * (GAME_WIDTH + 1), START_TOP * 3 + BOX_DIMENSION * 7))
        self.screen.blit(text2, (self.start_left * 4 + BOX_DIMENSION * (GAME_WIDTH + 1), START_TOP * 3 + BOX_DIMENSION * 9))

    def update_screen(self):
        pygame.display.update()

    def display(self, update_screen=True):
        self.clear_display()
        self.display_shadow()
        for row, col, blot in self.all_blots:
            self.draw_blot(blot, row, col)
        self.display_next_piece()
        self.display_score()
        if self.paused:
            self.display_pause()
        if update_screen:
            self.update_screen()

    def try_put(self, row: int, col: int, blot: Blot) -> bool:
        if not 0 <= row < GAME_HEIGHT or not 0 <= col < GAME_WIDTH:
            return False
        if not self.board[row][col].is_empty():
            return False
        self.board[row][col] = blot
        return True

    def put_or_die(self, row: int, col: int, blot: Blot):
        if not self.board[row][col].is_empty():
            raise GameOverException()
        self.board[row][col] = blot

    def put_new_tetrimono(self):
        piece = self.random_piece_generator.next()
        arrangement, color = piece.arrangement, piece.color

        piece_height = len(arrangement)
        piece_width = len(arrangement[0])

        point = Blot(BlotType.FALLING, piece=piece)
        point_center = Blot(BlotType.FALLING, piece=piece, is_center_blot=True)

        start_w = (GAME_WIDTH - piece_width) // 2
        for h in range(piece_height):
            for w in range(piece_width):
                if arrangement[h][w] == 1:
                    self.put_or_die(h, start_w + w, point)
                if arrangement[h][w] == 2:
                    self.put_or_die(h, start_w + w, point_center)

    def falling_freeze(self):
        for row, col, blot in self.all_blots:
            if blot.is_falling():
                self.board[row][col] = blot.to_placed_blot()

    def has_falling_tetrimono(self):
        for row in self.board:
            for point in row:
                if point.is_falling():
                    return True
        return False

    def add_points(self, points):
        self.points += points
        print('Points =', self.points)

    def add_points_for_elision(self, line_count):
        multiplier_for_line_count = {
            1: 40,
            2: 100,
            3: 300,
            4: 1200,
        }
        self.add_points(multiplier_for_line_count[line_count] * (self.level + 1))
        self.lines += line_count
        self.level = self.lines // 10

    def animate_elision(self, rows_to_elide: List[int]):
        for x in range(GAME_WIDTH):
            self.display(update_screen=False)
            for col in range(x + 1):
                for row in rows_to_elide:
                    self.draw_blot(self.board[row][col], row=row, column=col, color=(0, 0, 0))
            self.update_screen()
            # wait 20 frames
            yield

        for rowid in rows_to_elide:
            del self.board[rowid]
            self.board.insert(0, [Blot(BlotType.EMPTY)] * GAME_WIDTH)


    def elide_tetrises(self):
        rows_to_elide = []

        for row in range(GAME_HEIGHT):
            placed_in_row = [blot for blot in self.board[row] if blot.is_placed()]
            full_row = len(placed_in_row) == GAME_WIDTH
            if full_row:
                rows_to_elide.append(row)

        if len(rows_to_elide) != 0:
            self.add_points_for_elision(len(rows_to_elide))

            self.running_elision_animation = True
            self.elision_animation_generator = self.animate_elision(rows_to_elide)

    def save_game(self):
        with open(SAVE_PATH, "wb") as save_file:
            save_file.write(self.board_to_bin())

    def do_tick(self):
        if self.running_elision_animation:
            try:
                next(self.elision_animation_generator)
            except StopIteration:
                self.running_elision_animation = False
        elif self.frame % self.frames_per_gridcell() == 0:
            if self.has_falling_tetrimono():
                self.do_fall()
                self.elide_tetrises()
            else:
                self.save_game()
                self.put_new_tetrimono()
            self.display()
            # self.display_text()
        self.frame += 1

    def board_copy(self):
        return [row.copy() for row in self.board]

    # returns whether we froze the falling piece
    def do_fall(self):
        # freeze if we are at the last row
        for col in range(GAME_WIDTH):
            if self.board[GAME_HEIGHT - 1][col].is_falling():
                self.falling_freeze()
                return True
        board_before_fall = self.board_copy()
        for row in reversed(range(GAME_HEIGHT - 1)):
            for col in range(GAME_WIDTH):
                blot = self.board[row][col]

                if blot.is_falling():
                    if self.board[row + 1][col].is_placed():
                        self.board = board_before_fall
                        self.falling_freeze()
                        return True
                    self.put_or_die(row + 1, col, blot)
                    self.board[row][col] = Blot(BlotType.EMPTY)
        return False

    def falling_move_left(self):
        for row in self.board:
            if row[0].is_falling():
                return
            for pointLeft, pointRight in zip(row, row[1:]):
                if pointLeft.is_placed() and pointRight.is_falling():
                    return

        for row in self.board:
            for col in range(GAME_WIDTH):
                if row[col].is_falling():
                    row[col - 1] = row[col]
                    row[col] = Blot(BlotType.EMPTY)

    def falling_move_right(self):
        for row in self.board:
            if row[-1].is_falling():
                return
            for pointLeft, pointRight in zip(row, row[1:]):
                if pointLeft.is_falling() and pointRight.is_placed():
                    return

        for row in self.board:
            for col in reversed(range(GAME_WIDTH)):
                if row[col].is_falling():
                    row[col + 1] = row[col]
                    row[col] = Blot(BlotType.EMPTY)

    @property
    def all_blots(self):
        for row in range(GAME_HEIGHT):
            for col in range(GAME_WIDTH):
                yield (row, col, self.board[row][col])

    def falling_get_center_blot(self) -> Tuple[int, int, Optional[Blot]]:
        if not self.has_falling_tetrimono():
            return 0, 0, None

        return [
            (row, col, blot)
            for row, col, blot in self.all_blots
            if blot.is_falling() and blot.is_center_blot()
        ][0]

    def is_falling(self, row: int, col: int) -> bool:
        if not 0 <= row < GAME_HEIGHT or not 0 <= col < GAME_WIDTH:
            return False
        return self.board[row][col].is_falling()

    def falling_rotate_clockwise(self):
        center_row, center_col, center_blot = self.falling_get_center_blot()

        if not center_blot or not center_blot.should_rotate():
            return

        board_copy = self.board_copy()

        all_falling = []

        for row, col, blot in self.all_blots:
            if blot.is_falling() and not blot.is_center_blot():
                all_falling.append((row, col, blot))
                self.board[row][col] = Blot(BlotType.EMPTY)

        for row, col, blot in all_falling:
            row_center_offset = row - center_row
            col_center_offset = col - center_col

            rotated_row = center_row + col_center_offset
            rotated_col = center_col - row_center_offset

            if not self.try_put(rotated_row, rotated_col, blot):
                self.board = board_copy
                return


    def board_to_bin(self):
        out = bytearray()
        out += self.points.to_bytes(8, byteorder='big')
        out += self.lines.to_bytes(4, byteorder='big')
        out += self.level.to_bytes(4, byteorder='big')
        for i, (row, col, blot) in enumerate(self.all_blots):
            if i & 1 == 0:  # every second blot starting from the first
                out += bytes([blot.get_color_id() << 4])
            else:  # every second blot starting from the second one
                out[-1] |= blot.get_color_id()
        return out
        # TODO: points, center piece location (there's only one - should fit in a byte(?))


    @staticmethod
    def blot_from_id(id):
        if id == 0:
            return Blot(BlotType.EMPTY)
        piece = PIECES[(id & 0b111) - 1]
        if id & 0b1000 != 0:
            return Blot(BlotType.FALLING, piece=piece)
        else:
            return Blot(BlotType.PLACED, piece=piece)


    def set_blot_by_index(self, i, blot):
        self.board[i // GAME_WIDTH][i % GAME_WIDTH] = blot


    def bin_to_board(self, data):
        EXPECTED_SIZE = 16 + (GAME_HEIGHT * GAME_WIDTH) // 2
        if len(data) != EXPECTED_SIZE:
            print("Wrong save file size! Expected {} but got {}.".format(EXPECTED_SIZE, len(data)))
            return
        self.points = int.from_bytes(data[0:8], byteorder='big')
        self.lines = int.from_bytes(data[8:12], byteorder='big')
        self.level = int.from_bytes(data[12:16], byteorder='big')
        for i, byte in enumerate(data[16:]):
            i *= 2  # every byte has 2 blots in it
            self.set_blot_by_index(i, self.blot_from_id(byte >> 4))
            self.set_blot_by_index(i + 1, self.blot_from_id(byte & 0b1111))

    def try_load(self):
        with open(SAVE_PATH, "rb") as save_file:
            self.bin_to_board(save_file.read())

MenuResult = Enum('MenuResult', ['new_game', 'load_game'])
def menu(screen, font):
    position = 0
    position_range = (0, 2)
    while True:
        event = pygame.event.wait()
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            quit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                position += 1
            elif event.key == pygame.K_UP:
                position -= 1
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                if position == 0:
                    return MenuResult.new_game
                elif position == 1:
                    return MenuResult.load_game
                elif position == 2:
                    pygame.quit()
            position = min(position, position_range[1])
            position = max(position, position_range[0])

        pygame.draw.rect(screen, (0, 0, 0, 0), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        def draw_button(idx, label):
            shade = 100 if idx == position else 50
            BUTTON_WIDTH = 300
            BUTTON_HEIGHT = 80
            height = SCREEN_HEIGHT/4 + BUTTON_HEIGHT * 2 * idx
            pygame.draw.rect(screen, (shade, shade, shade, 0), 
                    (SCREEN_WIDTH/2 - BUTTON_WIDTH/2, height, BUTTON_WIDTH, BUTTON_HEIGHT))
            text = font.render(label, True, (240, 240, 240))
            text_rect = text.get_rect(center=(SCREEN_WIDTH/2, height + BUTTON_HEIGHT/2))
            screen.blit(text, text_rect)

        draw_button(0, "Start")
        draw_button(1, "Load last game")
        draw_button(2, "Exit")
        pygame.display.update()

def main():
    pygame.init()

    #
    pygame.mixer.quit()
    font = pygame.font.SysFont("monospace", 40)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    menu_result = menu(screen, font)

    game = Game(screen, font, REMOTE_GAME_LEFT_MARGIN)
    if menu_result == MenuResult.load_game:
        game.try_load()

    #game = MultiplayerGame(screen, font, REMOTE_GAME_LEFT_MARGIN)
    #remoteGame = MirroredRemoteGame(screen, font)

    TIMER_EVENT = pygame.USEREVENT

    pygame.time.set_timer(TIMER_EVENT, 1000 // 50)

    try:
        while True:
            event = pygame.event.wait()
            #print(event)
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                quit()
            elif not game.paused and event.type == TIMER_EVENT:
                game.do_tick()
                continue

            if not game.paused and game.running_elision_animation:
                continue  # Don't react to keystrokes while animating elision

            if event.type == pygame.KEYDOWN:
                key = event.key

                if key == pygame.K_p:
                    game.paused = not game.paused

                elif game.paused:
                    pass

                elif key == pygame.K_LEFT:
                    game.falling_move_left()

                elif key == pygame.K_RIGHT:
                    game.falling_move_right()

                elif key == pygame.K_x or key == pygame.K_UP:
                    game.falling_rotate_clockwise()

                elif key == pygame.K_DOWN:
                    if game.do_fall():
                        game.add_points(1)
                        game.elide_tetrises()
                        game.save_game()
                        game.put_new_tetrimono()

                elif key == pygame.K_SPACE:
                    if game.has_falling_tetrimono():
                        while not game.do_fall():
                            game.add_points(1)
                        game.elide_tetrises()
                        game.save_game()
                        game.put_new_tetrimono()

                #game.display_text()
                # Clear the whole screen
                game.display()
    except GameOverException:
        pass

if __name__ == '__main__':
    while True:
        main()
