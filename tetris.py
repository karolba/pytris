#!/usr/bin/env python3

import random
import string
import pygame
import sys
import os
import subprocess
import fcntl
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


# TODO: It would be great if this could be a @dataclass but charon.kis.agh.edu.pl has an outdated Python version
class Piece:
    def __init__(self, arrangement, color, can_be_first, id, long_tetrimono_rotation=False, no_rotation=False):
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
          id=0),

    Piece(arrangement=[[1, 2, 1, 0],
                       [0, 0, 1, 0]],
          color=(0x30, 0x30, 0xff),
          can_be_first=True,
          id=1),

    Piece(arrangement=[[1, 2, 1, 0],
                       [1, 0, 0, 0]],
          color=(0xff, 0xa5, 0x00),
          can_be_first=True,
          id=2),

    Piece(arrangement=[[1, 1, 0, 0],
                       [1, 2, 0, 0]],
          color=(0xff, 0xff, 0x00),
          no_rotation=True,
          can_be_first=True,
          id=3),

    Piece(arrangement=[[0, 1, 1, 0],
                       [1, 2, 0, 0]],
          color=(0x00, 0xff, 0x00),
          can_be_first=False,
          id=4),

    Piece(arrangement=[[1, 2, 1, 0],
                       [0, 1, 0, 0]],
          color=(0x80, 0x00, 0x80),
          can_be_first=True,
          id=5),

    Piece(arrangement=[[1, 2, 0, 0],
                       [0, 1, 1, 0]],
          color=(0xff, 0x00, 0x00),
          can_be_first=False,
          id=6),
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


class GameOverException(Exception):
    pass


class Game:
    def __init__(self, screen, font, master, send_to_network=None, invite_code=None):
        self.screen = screen
        self.random_piece_generator = RandomPieceGenerator()
        self.level = 0
        self.points = 0
        self.frame = 0
        self.lines = 0
        self.font = font
        self.board: List[List[Blot]] = []
        self.running_elision_animation = False
        self.elision_animation_generator = None
        self.send_to_network = send_to_network
        self.invite_code = invite_code
        self.master = master
        for _ in range(GAME_HEIGHT):
            self.board.append([Blot(BlotType.EMPTY)] * GAME_WIDTH)

    def frames_per_gridcell(self) -> int:
        level_to_frames = {
            0: 36,
            1: 32,
            2: 29,
            3: 25,
            4: 22,
            5: 18,
            6: 15,
            7: 11,
            8: 7,
            9: 5,
            10: 4,
            11: 4,
            12: 4,
            13: 3,
            14: 3,
            15: 3,
            16: 2,
            17: 2,
            18: 2,
        }
        if self.level > 18:
            return 1
        return level_to_frames[self.level]

    def display_text(self):
        for row in self.board:
            for piece in row:
                print('-' if piece.is_empty() else 'x', end='')
            print()

    def draw_blot(self, blot: Blot, row=0, column=0, start_dimensions=(START_LEFT, START_TOP), color=None):
        left = start_dimensions[0] + column * BOX_DIMENSION
        top = start_dimensions[1] + row * BOX_DIMENSION

        if not blot.is_empty():
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
        # Clear the whole screen
        pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        # Black game background
        height = BOX_DIMENSION * GAME_HEIGHT
        width = BOX_DIMENSION * GAME_WIDTH
        pygame.draw.rect(self.screen, (0, 0, 0), (START_LEFT, START_TOP, width, height))

    def display_next_piece(self):
        top = START_TOP * 3
        left = START_LEFT * 4 + (BOX_DIMENSION * GAME_WIDTH)

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
            self.do_fall(even_if_slave=True)

        self.board = board

        return falling

    def display_shadow(self):
        for row, col, blot in self.shadow_location():
            self.draw_blot(blot, row, col, color=(40, 40, 40))

    def display_text_line(self, text, row):
        rendered = self.font.render(text, 1, (127, 127, 127))
        self.screen.blit(rendered, (START_LEFT * 4 + BOX_DIMENSION * (GAME_WIDTH + 1), START_TOP * 3 + BOX_DIMENSION * row))

    def display_score(self):
        self.display_text_line("Score: %s" % self.points, 7)
        self.display_text_line("Level: %s" % self.level, 9)
        if self.invite_code:
            self.display_text_line("Invite code: %s" % self.invite_code, 11)
        if self.master:
            self.display_text_line("Your turn!", 13)

    def update_screen(self):
        pygame.display.update()

    def display(self, update_screen=True):
        self.clear_display()
        self.display_shadow()
        for row, col, blot in self.all_blots:
            self.draw_blot(blot, row, col)
        self.display_next_piece()
        self.display_score()
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
        if not self.master:
            return

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
        if not self.master:
            return
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

    def do_tick(self):
        if self.running_elision_animation:
            try:
                next(self.elision_animation_generator)
            except StopIteration:
                self.running_elision_animation = False
        elif self.frame % self.frames_per_gridcell() == 0:
            if self.has_falling_tetrimono():
                if self.do_fall():
                    self.elide_tetrises()
                    self.master = False
                else:
                    self.elide_tetrises()
            else:
                self.put_new_tetrimono()
            self.display()
            if self.master and self.send_to_network:
                self.send_to_network(self)
            # self.display_text()
        self.frame += 1

    def board_copy(self):
        return [row.copy() for row in self.board]

    # returns whether we froze the falling piece
    def do_fall(self, even_if_slave=False):
        if not self.master:
            if not even_if_slave:
                return False
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

        centers = [
            (row, col, blot)
            for row, col, blot in self.all_blots
            if blot.is_falling() and blot.is_center_blot()
        ]
        if len(centers) != 1:
            print("There should be only one center blot at any given time: ", centers)
        if len(centers) == 0:
            return 0, 0, None
        return centers[0]

    def is_falling(self, row: int, col: int) -> bool:
        if not 0 <= row < GAME_HEIGHT or not 0 <= col < GAME_WIDTH:
            return False
        return self.board[row][col].is_falling()

    def falling_rotate_clockwise(self):
        self.falling_rotate(1)

    def falling_rotate_counterclockwise(self):
        self.falling_rotate(-1)

    def falling_rotate(self, rotation: int):
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

            rotated_row = center_row + rotation * col_center_offset
            rotated_col = center_col - rotation * row_center_offset

            if not self.try_put(rotated_row, rotated_col, blot):
                self.board = board_copy
                return

    def serialize(self) -> bytes:
        out = b''

        opponent_should_be_master = not self.master
        out += b'\2' if opponent_should_be_master else b'\1'

        for _, _, blot in self.all_blots:
            if blot.is_empty():
                out += b'\1'
            elif blot.is_falling() and blot.is_center_blot():
                print("SENT CENTEr")
                out += (blot._piece.id + 60).to_bytes(1, byteorder='big')
            elif blot.is_falling():
                out += (blot._piece.id + 30).to_bytes(1, byteorder='big')
            else:
                out += (blot._piece.id + 2).to_bytes(1, byteorder='big')
        return out

    def unserialize(self, data: bytes):
        should_be_master = data[0] == 2
        if should_be_master:
            self.master = True
        data = data[1:]
        for i, byte in enumerate(data):
            row = i // GAME_WIDTH
            col = i % GAME_WIDTH
            if byte == 1:
                blot = Blot(BlotType.EMPTY)
            elif byte >= 60:
                print("GOT A CENTER")
                id = byte - 60
                blot = Blot(BlotType.FALLING, piece=PIECES[id], is_center_blot=True)
            elif byte >= 30:
                id = byte - 30
                blot = Blot(BlotType.FALLING, piece=PIECES[id])
            else:
                id = byte - 2
                blot = Blot(BlotType.PLACED, piece=PIECES[id])
            self.board[row][col] = blot


def check_network(client_process: subprocess.Popen, game: Game):
    try:
        line = client_process.stdout.readline()
        if line == b'':
            return

        if line[-1] == ord(b'\n'):
            line = line[0 : -1]

        if len(line) != GAME_WIDTH * GAME_HEIGHT + 1:
            print("Bad received length? ", len(line), "!=", GAME_HEIGHT*GAME_WIDTH+1)
            return
        game.unserialize(line)
        game.display()
    except IOError:
        pass


def send_to_network(client_process: subprocess.Popen, game: Game):
    client_process.stdin.write(game.serialize() + b'\n')
    client_process.stdin.flush()
    pass


def start_client_process(is_master, code) -> subprocess.Popen:
    arg = '--master' if is_master else '--slave'

    client_process = subprocess.Popen([sys.executable, './client.py', arg, code],
                                      stdout=subprocess.PIPE, stdin=subprocess.PIPE)

    # nonblocking pipe
    fl = fcntl.fcntl(client_process.stdout, fcntl.F_GETFL)
    fcntl.fcntl(client_process.stdout, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    return client_process


def random_invite_code() -> str:
    return ''.join(random.choices(string.ascii_lowercase, k=4))


def game(multi: bool, master: Optional[bool] = None, invite_code=None):
    client_process = None
    if multi:
        client_process = start_client_process(master, invite_code)
        game = Game(screen, font, master, lambda game: send_to_network(client_process, game), invite_code=invite_code)
    else:
        game = Game(screen, font, master=True)

    TIMER_EVENT = pygame.USEREVENT
    CHECK_NETWORK_EVENT = pygame.USEREVENT + 1

    pygame.time.set_timer(TIMER_EVENT, 1000 // 50)
    if multi:
        pygame.time.set_timer(CHECK_NETWORK_EVENT, 1000 // 300)

    while True:
        event = pygame.event.wait()
        # print(event)
        if event.type == pygame.QUIT:
            return
        elif event.type == TIMER_EVENT:
            game.do_tick()
            continue
        elif event.type == CHECK_NETWORK_EVENT:
            check_network(client_process, game)

        if game.running_elision_animation:
            continue  # Don't react to keystrokes while animating elision

        if event.type == pygame.KEYDOWN:
            key = event.key

            if not game.master:
                pass

            elif key == pygame.K_LEFT:
                game.falling_move_left()

            elif key == pygame.K_RIGHT:
                game.falling_move_right()

            elif key == pygame.K_x or key == pygame.K_UP:
                game.falling_rotate_clockwise()

            elif key == pygame.K_z:
                game.falling_rotate_counterclockwise()

            elif key == pygame.K_DOWN:
                if game.do_fall():
                    game.add_points(1)
                    game.elide_tetrises()
                    game.put_new_tetrimono()

            elif key == pygame.K_SPACE:
                if game.has_falling_tetrimono():
                    while not game.do_fall(even_if_slave=True):
                        game.add_points(1)
                    game.elide_tetrises()
                    game.put_new_tetrimono()

            # game.display_text()
            game.display()

def draw_button(id: int, selected: bool):
    labels = ['Singleplayer', 'Multiplayer: invite', 'Multiplayer: join']

    width = SCREEN_WIDTH // 4
    height = SCREEN_HEIGHT // 12
    top = ((2 + 3 * id) / 12) * SCREEN_HEIGHT
    color = (60, 60, 60) if not selected else (130, 130, 130)
    pygame.draw.rect(screen, color, (SCREEN_WIDTH/2 - width/2, top, width, height))

    text_color = (200, 200, 200) if not selected else (255, 255, 255)
    text = font.render(labels[id], True, text_color)
    text_rect = text.get_rect(center=(SCREEN_WIDTH / 2, top + height / 2))
    screen.blit(text, text_rect)

def draw_menu(choice: int):
    # Clear the whole screen
    pygame.draw.rect(screen, (0, 0, 0), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
    for x in range(3):
        draw_button(x, x == choice)
    pygame.display.update()

def draw_ask_for_code_box(code):
    width = SCREEN_WIDTH / 3
    height = SCREEN_HEIGHT / 5

    pygame.draw.rect(screen, (0, 0, 0), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.draw.rect(screen, (30, 30, 30), (SCREEN_WIDTH/2 - width/2, SCREEN_HEIGHT/2 - height/2, width, height))

    text = font.render("Invite code: %s" % code, True, (230, 230, 230))
    screen.blit(text, (SCREEN_WIDTH/2 - width/2 + 10, SCREEN_HEIGHT/2 - height/2 + 10))
    pygame.display.update()

def ask_for_code():
    str = ""
    draw_ask_for_code_box(str)
    while True:
        event = pygame.event.wait()
        if event.type == pygame.QUIT:
            return
        if event.type == pygame.KEYDOWN:
            key = event.key

            if key == pygame.K_RETURN and len(str) == 4:
                return str
            elif key == pygame.K_BACKSPACE and len(str) > 0:
                str = str[0 : -1]
            else:
                str += event.unicode
            draw_ask_for_code_box(str)


def menu():
    choice = 0

    draw_menu(choice)

    while True:
        event = pygame.event.wait()
        if event.type == pygame.QUIT:
            return
        if event.type == pygame.KEYDOWN:
            key = event.key

            if key == pygame.K_DOWN:
                choice = min(2, choice + 1)
                draw_menu(choice)
            elif key == pygame.K_UP:
                choice = max(0, choice - 1)
                draw_menu(choice)
            elif key == pygame.K_RETURN or key == pygame.K_SPACE:
                return choice


def main():
    global font, screen

    pygame.init()
    pygame.mixer.quit()

    pygame.display.set_caption('Tetris')

    font = pygame.font.SysFont("monospace", 40)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    game_mode = menu()
    if game_mode == 0:
        game(multi=False)
    elif game_mode == 1:
        game(multi=True, master=True, invite_code=random_invite_code())
    elif game_mode == 2:
        invite_code = ask_for_code()
        game(multi=True, master=False, invite_code=invite_code)

if __name__ == '__main__':
    main()
