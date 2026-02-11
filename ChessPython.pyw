import os
import pygame
import chess
import socket
import threading

# Размеры игрового окна и фпс
WIDTH, HEIGHT = 512, 512
SQ_SIZE = WIDTH // 8
FPS = 30

# Директории
current_directory = os.path.dirname(__file__)
assets_directory = os.path.join(current_directory, "assets")

# Инициализация игры
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Network Chess")
clock = pygame.time.Clock()

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LIGHT_BROWN = (240, 217, 181)
DARK_BROWN = (181, 136, 99)
HIGHLIGHT_COLOR = (0, 255, 0, 100)
CHECK_HIGHLIGHT = (255, 0, 0, 100)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER_COLOR = (100, 149, 237)
TEXT_COLOR = (255, 255, 255)

# Загрузка спрайтов фигур
images = {}

def load_images():
    figures = ['wp', 'wr', 'wn', 'wb', 'wk', 'wq', 'bp', 'br', 'bn', 'bb', 'bk', 'bq']
    for role in figures:
        images[role] = pygame.transform.scale(
            pygame.image.load(os.path.join(assets_directory, role + '.png')),
            (SQ_SIZE, SQ_SIZE)
        )

# Мультиплеер
class Network:
    def __init__(self, host, port, is_server=False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if is_server:
            self.sock.bind((host, port))
            self.sock.listen(1)
            print("Waiting for connection...")
            self.conn, _ = self.sock.accept()
            print("Connection established.")
        else:
            self.sock.connect((host, port))

    def send(self, data):
        if hasattr(self, 'conn'):
            self.conn.sendall(data.encode())
        else:
            self.sock.sendall(data.encode())

    def receive(self):
        if hasattr(self, 'conn'):
            return self.conn.recv(1024).decode()
        else:
            return self.sock.recv(1024).decode()


# Игра
class ChessGame:

    # Инициализация
    def __init__(self, network, is_white):
        self.board = chess.Board()
        self.selected_square = None
        self.legal_moves = []
        self.winner = None
        self.network = network
        self.is_white = is_white
        self.my_turn = is_white

    # Рисуем доску
    def draw_board(self):
        colors = [LIGHT_BROWN, DARK_BROWN]
        for row in range(8):
            for col in range(8):
                color = colors[(row + col) % 2]
                pygame.draw.rect(screen, color, pygame.Rect(col * SQ_SIZE, row * SQ_SIZE, SQ_SIZE, SQ_SIZE))


    # Рисуем фигуры
    def draw_pieces(self):
        for square, piece in self.board.piece_map().items():
            file, rank = chess.square_file(square), chess.square_rank(square)
            if not self.is_white:
                file, rank = 7 - file, 7 - rank
            x = file * SQ_SIZE
            y = (7 - rank) * SQ_SIZE
            role = piece.symbol().lower()
            color = 'w' if piece.color else 'b'
            screen.blit(images[color + role], pygame.Rect(x, y, SQ_SIZE, SQ_SIZE))

    # Рисуем подсветку возможных ходов и короля под шахом
    def draw_highlights(self):
        if self.board.is_check() and not self.winner:
            king_square = self.board.king(self.board.turn)
            if king_square is not None:
                file, rank = chess.square_file(king_square), chess.square_rank(king_square)
                if not self.is_white:
                    file, rank = 7 - file, 7 - rank
                x = file * SQ_SIZE
                y = (7 - rank) * SQ_SIZE
                pygame.draw.rect(screen, CHECK_HIGHLIGHT, pygame.Rect(x, y, SQ_SIZE, SQ_SIZE), 5)

        for move in self.legal_moves:
            file, rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)
            if not self.is_white:
                file, rank = 7 - file, 7 - rank
            x = file * SQ_SIZE
            y = (7 - rank) * SQ_SIZE
            pygame.draw.rect(screen, HIGHLIGHT_COLOR, pygame.Rect(x, y, SQ_SIZE, SQ_SIZE), 3)

        if self.selected_square is not None:
            file, rank = chess.square_file(self.selected_square), chess.square_rank(self.selected_square)
            if not self.is_white:
                file, rank = 7 - file, 7 - rank
            x = file * SQ_SIZE
            y = (7 - rank) * SQ_SIZE
            pygame.draw.rect(screen, HIGHLIGHT_COLOR, pygame.Rect(x, y, SQ_SIZE, SQ_SIZE), 5)


    # Конец игры
    def draw_winner(self):
        if not self.winner:
            return

        font = pygame.font.Font(None, 72)

        # Определяем сообщение на основе цвета игрока и победителя
        if self.stalemate:
            text = "Stalemate!"
            
        elif (self.is_white and self.winner == "White") or (not self.is_white and self.winner == "Black"):
            text = "You Win!"
        else:
            text = "You Lose!"

        # Рисуем сообщение
        text_surface = font.render(text, True, BLACK)
        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50))
        screen.blit(text_surface, text_rect)

        # Рисуем кнопку "New Game"
        button_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 20, 200, 50)
        pygame.draw.rect(screen, BUTTON_COLOR, button_rect)
        font = pygame.font.Font(None, 36)
        button_text_surface = font.render("New Game", True, TEXT_COLOR)
        button_text_rect = button_text_surface.get_rect(center=button_rect.center)
        screen.blit(button_text_surface, button_text_rect)


    # Обработка кликов
    def handle_click(self, x, y):
        if self.winner:
            # Проверяем, нажата ли кнопка "New Game"
            button_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 20, 200, 50)
            if button_rect.collidepoint(x, y):
                self.network.send("reset")  # Отправляем сигнал оппоненту
                self.reset_game()
            return

        if not self.my_turn:
            return

        file, rank = x // SQ_SIZE, 7 - y // SQ_SIZE
        if not self.is_white:
            file, rank = 7 - file, 7 - rank
        square = chess.square(file, rank)

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                self.legal_moves = [move for move in self.board.legal_moves if move.from_square == square]

        else:
            move = chess.Move(self.selected_square, square)
            if move in self.legal_moves:
                self.board.push(move)
                self.network.send(str(move))
                self.my_turn = False

                if self.board.is_checkmate():
                    self.winner = "White" if not self.board.turn else "Black"
                    # Отправляем сообщение о результате другому игроку
                    self.network.send(f"result {self.winner}")

            self.selected_square = None
            self.legal_moves = []


    # Ход оппонента
    def handle_opponent_move(self, move):
        move = chess.Move.from_uci(move)
        self.board.push(move)
        self.my_turn = True
        print("Opponent's move handled. It's now your turn.")


    # Новая игра
    def reset_game(self):
        self.board = chess.Board()
        self.selected_square = None
        self.legal_moves = []
        self.winner = None

        # Меняем цвет фигур
        self.is_white = not self.is_white
        self.my_turn = self.is_white


# Рисуем кнопки
def draw_button(text, x, y, w, h, hover=False):
    color = BUTTON_HOVER_COLOR if hover else BUTTON_COLOR
    pygame.draw.rect(screen, color, (x, y, w, h))
    font = pygame.font.Font(None, 36)
    text_surf = font.render(text, True, TEXT_COLOR)
    text_rect = text_surf.get_rect(center=(x + w // 2, y + h // 2))
    screen.blit(text_surf, text_rect)

# Главное меню
def main_menu():
    load_images()
    running = True

    while running:
        screen.fill(WHITE)
        mx, my = pygame.mouse.get_pos()

        host_hover = 150 < mx < 350 and 200 < my < 250
        join_hover = 150 < mx < 350 and 300 < my < 350

        draw_button("Host Game", 150, 200, 200, 50, host_hover)
        draw_button("Join Game", 150, 300, 200, 50, join_hover)

        # Обработка нажатий на кнопки
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if host_hover:
                    return True  # Host game
                elif join_hover:
                    return False  # Join game

        pygame.display.flip()
        clock.tick(FPS)

def main():
    is_server = main_menu()
    host = 'localhost' # Локальная сеть
    port = 65432

    if is_server:
        network = Network(host, port, is_server=True)
        is_white = True
    else:
        network = Network(host, port)
        is_white = False

    game = ChessGame(network, is_white)
    running = True

    # Поток приема сообщений
    def receive_thread():
        while running:
            try:
                data = network.receive()
                if data == "reset":
                    game.reset_game()
                elif data.startswith("result"):
                    _, winner_color = data.split()
                    game.winner = winner_color  # Устанавливаем победителя у обоих игроков
                else:
                    game.handle_opponent_move(data)
            except Exception as e:
                print("Error:", e)
                break
    
    threading.Thread(target=receive_thread, daemon=True).start()

    # Бесконечный цикл для того чтобы окно было все время до нажатия кнопки выхода
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                game.handle_click(x, y)

        game.draw_board()
        game.draw_pieces()
        game.draw_highlights()
        game.draw_winner()
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

# Стандартная python конструкция, которая гарантирует, что игра была открыта как файл
if __name__ == "__main__":
    main()
