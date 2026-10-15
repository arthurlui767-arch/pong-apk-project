import json
import math
import os
import random
import sys
from pathlib import Path

import pygame


HIGH_SCORE_PATH = (
    Path(os.environ.get("APPDATA", str(Path.home()))) / "Pong" / "high_scores.json"
)
WIDTH = 900
HEIGHT = 600
FPS = 60
PADDLE_WIDTH = 18
PADDLE_HEIGHT = 120
PLAYER_SPEED = 8
BALL_RADIUS = 12
BALL_SPEED = 7
MASSIVE_BALL_MULTIPLIER = 6.0
BOT_DIFFICULTIES = {
    "Fácil": {"speed": 3, "deadzone": 38, "predict": False},
    "Normal": {"speed": 5, "deadzone": 20, "predict": True},
    "Difícil": {"speed": 7, "deadzone": 5, "predict": True},
}
BOT_VS_BOT_EXTRA_DIFFICULTIES = {
    "Quase impossível": {
        "speed": 32,
        "deadzone": 0,
        "predict": True,
        "snap_tracking": True,
    },
}
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
BACKGROUND = (11, 17, 29)
PANEL = (20, 29, 45)
MUTED = (139, 155, 177)
ACCENT = (79, 226, 177)
BLUE = (100, 164, 255)
CORAL = (237, 115, 105)
GOLD = (255, 196, 100)
PALE = (235, 232, 211)


def create_display() -> pygame.Surface:
    if sys.platform == "android":
        return pygame.display.set_mode(
            (WIDTH, HEIGHT),
            pygame.FULLSCREEN | pygame.SCALED,
        )
    return pygame.display.set_mode((WIDTH, HEIGHT))


class Paddle:
    def __init__(self, x: int, y: int, speed: int, height: int = PADDLE_HEIGHT) -> None:
        self.rect = pygame.Rect(x, y, PADDLE_WIDTH, height)
        self.speed = speed

    def move(self, direction: int) -> None:
        self.rect.y += direction * self.speed
        self.rect.y = max(0, min(HEIGHT - self.rect.height, self.rect.y))


class Ball:
    def __init__(self, speed: int = BALL_SPEED) -> None:
        self.base_speed = speed
        self.speed_multiplier = 1.0
        self.rect = pygame.Rect(
            WIDTH // 2 - BALL_RADIUS,
            HEIGHT // 2 - BALL_RADIUS,
            BALL_RADIUS * 2,
            BALL_RADIUS * 2,
        )
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.pulse = random.uniform(0.0, math.tau)
        self.hit_flash = 0.0
        self.glow_strength = 0.0
        self.reset(direction=random.choice([-1, 1]))

    def update_effects(self) -> None:
        self.pulse += 0.18
        self.hit_flash = max(0.0, self.hit_flash - 0.12)
        self.glow_strength = max(0.0, self.glow_strength - 0.08)

    def trigger_hit_effect(self) -> None:
        self.hit_flash = 1.0
        self.glow_strength = 1.0

    def reset(self, direction: int) -> None:
        self.rect.center = (WIDTH // 2, HEIGHT // 2)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        angle = random.uniform(-0.9, 0.9)
        current_speed = self.base_speed * self.speed_multiplier
        self.speed_x = direction * current_speed
        self.speed_y = angle * current_speed * 1.4
        self.trigger_hit_effect()

    def set_multiplier(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("A velocidade da bola deve ser maior que zero.")
        if multiplier == self.speed_multiplier:
            return
        ratio = multiplier / self.speed_multiplier
        self.speed_x *= ratio
        self.speed_y *= ratio
        self.speed_multiplier = multiplier

    def set_slow(self, enabled: bool) -> None:
        self.set_multiplier(0.55 if enabled else 1.0)

    def set_massive(self, enabled: bool) -> None:
        self.set_multiplier(MASSIVE_BALL_MULTIPLIER if enabled else 1.0)

    def _bounce_from_paddle(self, paddle: Paddle, direction: int) -> None:
        if direction > 0:
            self.rect.left = paddle.rect.right
        else:
            self.rect.right = paddle.rect.left
        self.x = float(self.rect.x)
        relative_hit = (self.rect.centery - paddle.rect.centery) / (
            paddle.rect.height / 2 + BALL_RADIUS
        )
        angle = max(-1.0, min(1.0, relative_hit)) * 1.05
        speed = self.base_speed * self.speed_multiplier
        self.speed_x = direction * speed * math.cos(angle)
        self.speed_y = speed * math.sin(angle)
        self.trigger_hit_effect()

    def update(self, left_paddle: Paddle, right_paddle: Paddle) -> tuple[int, int]:
        self.update_effects()
        largest_step = max(abs(self.speed_x), abs(self.speed_y))
        substeps = max(1, math.ceil(largest_step / 5))

        for _ in range(substeps):
            self.x += self.speed_x / substeps
            self.y += self.speed_y / substeps
            self.rect.topleft = (round(self.x), round(self.y))

            if self.rect.top <= 0:
                self.rect.top = 0
                self.y = float(self.rect.y)
                self.speed_y = abs(self.speed_y)
            elif self.rect.bottom >= HEIGHT:
                self.rect.bottom = HEIGHT
                self.y = float(self.rect.y)
                self.speed_y = -abs(self.speed_y)

            if self.speed_x < 0 and self.rect.colliderect(left_paddle.rect):
                self._bounce_from_paddle(left_paddle, direction=1)
            elif self.speed_x > 0 and self.rect.colliderect(right_paddle.rect):
                self._bounce_from_paddle(right_paddle, direction=-1)

        score_left = 0
        score_right = 0

        if self.rect.right <= 0:
            score_right = 1
            self.reset(direction=1)
        elif self.rect.left >= WIDTH:
            score_left = 1
            self.reset(direction=-1)

        return score_left, score_right


class PongGame:
    def __init__(
        self,
        mode: str,
        difficulty: str = "Normal",
        admin_mode: bool = False,
        ball_speed: int = BALL_SPEED,
        paddle_height: int = PADDLE_HEIGHT,
        multiball_mode: bool = False,
    ) -> None:
        pygame.init()
        self.mode = mode
        self.difficulty = difficulty
        self.admin_mode = admin_mode
        self.admin_paddle_enabled = False
        self.multiball_mode = multiball_mode
        if mode == "bot_vs_bot" and difficulty in BOT_VS_BOT_EXTRA_DIFFICULTIES:
            self.bot_settings = BOT_VS_BOT_EXTRA_DIFFICULTIES[difficulty]
        else:
            self.bot_settings = BOT_DIFFICULTIES[difficulty]
        paddle_height = max(
            paddle_height,
            self.bot_settings.get("paddle_height", PADDLE_HEIGHT),
        )
        self.base_paddle_height = paddle_height
        self.paddle_height = paddle_height
        self.screen = create_display()
        pygame.display.set_caption("Pong")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 64)
        self.small_font = pygame.font.SysFont(None, 28)
        self.record_font = pygame.font.SysFont(None, 22)
        self.left_score = 0
        self.right_score = 0
        self.high_scores = self._load_high_scores()
        self.ball_trail: list[tuple[int, int]] = []
        self.arena_background = self.create_arena_background()

        self.left_paddle = Paddle(
            30,
            HEIGHT // 2 - paddle_height // 2,
            PLAYER_SPEED,
            paddle_height,
        )
        self.right_paddle = Paddle(
            WIDTH - 30 - PADDLE_WIDTH,
            HEIGHT // 2 - paddle_height // 2,
            self.bot_settings["speed"] if mode != "players" else PLAYER_SPEED,
            paddle_height,
        )
        self.left_paddle.speed = self.bot_settings["speed"] if mode == "bot_vs_bot" else PLAYER_SPEED
        self.balls = [Ball(ball_speed)]
        self.ball = self.balls[0]

    @staticmethod
    def create_arena_background() -> pygame.Surface:
        background = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            blend = y / HEIGHT
            color = (
                int(8 + 5 * blend),
                int(13 + 7 * blend),
                int(23 + 12 * blend),
            )
            pygame.draw.line(background, color, (0, y), (WIDTH, y))
        pygame.draw.line(background, (27, 42, 57), (24, 0), (24, HEIGHT), 1)
        pygame.draw.line(background, (27, 42, 57), (WIDTH - 25, 0), (WIDTH - 25, HEIGHT), 1)
        for y in range(14, HEIGHT, 30):
            pygame.draw.line(
                background,
                (38, 54, 70),
                (WIDTH // 2, y),
                (WIDTH // 2, y + 14),
                2,
            )
        return background

    @staticmethod
    def _load_high_scores() -> dict[str, int]:
        try:
            data = json.loads(HIGH_SCORE_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

        if not isinstance(data, dict) or any(
            not isinstance(key, str)
            or not isinstance(score, int)
            or isinstance(score, bool)
            or score < 0
            for key, score in data.items()
        ):
            raise ValueError(f"Arquivo de recordes inválido: {HIGH_SCORE_PATH}")
        return data

    def _save_high_scores(self) -> None:
        if self.mode not in ("bot", "players"):
            return

        updated = False
        for side, score in (("left", self.left_score), ("right", self.right_score)):
            key = f"{self.mode}_{side}"
            if score > self.high_scores.get(key, 0):
                self.high_scores[key] = score
                updated = True

        if updated:
            HIGH_SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            HIGH_SCORE_PATH.write_text(
                json.dumps(self.high_scores, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _spawn_extra_ball(self) -> None:
        if not self.multiball_mode:
            return
        base = self.ball.base_speed
        new_ball = Ball(base)
        new_ball.speed_multiplier = self.ball.speed_multiplier
        new_ball.speed_x = random.choice([-1, 1]) * base * self.ball.speed_multiplier
        new_ball.speed_y = random.uniform(-1.0, 1.0) * base * self.ball.speed_multiplier * 1.4
        self.balls.append(new_ball)

    def _ensure_multiball_state(self) -> None:
        if not self.multiball_mode:
            return
        target = 1 + max(self.left_score, self.right_score) // 2
        while len(self.balls) < target:
            self._spawn_extra_ball()

    def update_bot(self, paddle: Paddle, is_left: bool) -> None:
        approaching = self.ball.speed_x < 0 if is_left else self.ball.speed_x > 0
        if not approaching:
            target = HEIGHT // 2
        elif self.bot_settings["predict"]:
            paddle_x = paddle.rect.centerx
            frames_to_reach = abs(paddle_x - self.ball.rect.centerx) / max(
                abs(self.ball.speed_x), 1
            )
            projected_y = self.ball.rect.centery + self.ball.speed_y * frames_to_reach
            bounce_height = HEIGHT - BALL_RADIUS * 2
            reflected_y = (projected_y - BALL_RADIUS) % (2 * bounce_height)
            target = round(
                BALL_RADIUS
                + (
                    reflected_y
                    if reflected_y <= bounce_height
                    else 2 * bounce_height - reflected_y
                )
            )
        else:
            target = self.ball.rect.centery

        difference = target - paddle.rect.centery
        if self.bot_settings.get("snap_tracking", False):
            paddle.rect.centery = target
            paddle.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
            return

        deadzone = self.bot_settings["deadzone"]
        if difference > deadzone:
            paddle.move(1)
        elif difference < -deadzone:
            paddle.move(-1)

    def update_players(self) -> None:
        if self.mode == "players":
            keys = pygame.key.get_pressed()
            if keys[pygame.K_w]:
                self.left_paddle.move(-1)
            if keys[pygame.K_s]:
                self.left_paddle.move(1)
            if keys[pygame.K_UP]:
                self.right_paddle.move(-1)
            if keys[pygame.K_DOWN]:
                self.right_paddle.move(1)

    def handle_touch(self, event: pygame.event.Event) -> None:
        if event.type not in (pygame.FINGERDOWN, pygame.FINGERMOTION):
            return
        touch_x = round(event.x * WIDTH)
        touch_y = round(event.y * HEIGHT)
        if self.mode == "bot":
            if touch_x >= WIDTH // 2:
                return
            paddle = self.left_paddle
        elif self.mode == "players":
            paddle = self.left_paddle if touch_x < WIDTH // 2 else self.right_paddle
        else:
            return
        paddle.rect.centery = touch_y
        paddle.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

    def toggle_admin_slow(self) -> None:
        multiplier = 1.0 if self.ball.speed_multiplier == 0.55 else 0.55
        for ball in self.balls:
            ball.set_multiplier(multiplier)

    def toggle_admin_massive(self) -> None:
        multiplier = (
            1.0
            if self.ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER
            else MASSIVE_BALL_MULTIPLIER
        )
        for ball in self.balls:
            ball.set_multiplier(multiplier)

    def toggle_admin_paddle(self) -> None:
        self.admin_paddle_enabled = not self.admin_paddle_enabled
        self.paddle_height = (
            min(HEIGHT - 40, self.base_paddle_height + 50)
            if self.admin_paddle_enabled
            else self.base_paddle_height
        )
        center_y = self.left_paddle.rect.centery
        self.left_paddle.rect.height = self.paddle_height
        self.left_paddle.rect.centery = center_y
        self.left_paddle.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

    def draw(self) -> None:
        self.screen.blit(self.arena_background, (0, 0))

        pygame.draw.rect(
            self.screen,
            (16, 25, 38),
            self.left_paddle.rect.inflate(8, 8),
            border_radius=9,
        )
        pygame.draw.rect(self.screen, WHITE, self.left_paddle.rect, border_radius=6)
        right_color = BLUE if self.mode == "players" else ACCENT
        pygame.draw.rect(
            self.screen,
            (16, 25, 38),
            self.right_paddle.rect.inflate(8, 8),
            border_radius=9,
        )
        pygame.draw.rect(self.screen, right_color, self.right_paddle.rect, border_radius=6)

        for ball in self.balls:
            ball_color = CORAL if ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER else WHITE
            if ball is self.ball:
                for index, point in enumerate(self.ball_trail[-10:]):
                    radius = max(2, BALL_RADIUS * (index + 1) // 12)
                    pygame.draw.circle(
                        self.screen,
                        (104, 44, 57) if ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER else GRAY,
                        point,
                        radius,
                    )

            glow_radius = BALL_RADIUS + 12 + int(math.sin(ball.pulse) * 6)
            glow_size = glow_radius * 2 + 18
            glow_surface = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            glow_alpha = int(30 + ball.glow_strength * 120 + ball.hit_flash * 90)
            glow_color = (
                (237, 115, 105, glow_alpha)
                if ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER
                else (100, 164, 255, glow_alpha)
            )
            pygame.draw.circle(
                glow_surface,
                glow_color,
                (glow_size // 2, glow_size // 2),
                glow_radius,
            )
            self.screen.blit(
                glow_surface,
                (
                    ball.rect.centerx - glow_size // 2,
                    ball.rect.centery - glow_size // 2,
                ),
                special_flags=pygame.BLEND_ALPHA_SDL2,
            )

            shadow_offset = 5
            pygame.draw.circle(
                self.screen,
                (12, 17, 28),
                (ball.rect.centerx + shadow_offset, ball.rect.centery + shadow_offset),
                BALL_RADIUS + 5,
            )
            if ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER:
                pygame.draw.circle(self.screen, (100, 35, 48), ball.rect.center, BALL_RADIUS + 8, 2)
            else:
                pygame.draw.circle(self.screen, (55, 78, 99), ball.rect.center, BALL_RADIUS + 4, 1)
            pygame.draw.circle(
                self.screen,
                (255, 255, 255) if ball.hit_flash > 0.25 else ball_color,
                ball.rect.center,
                BALL_RADIUS,
            )
            inner_core = BALL_RADIUS - 4
            pygame.draw.circle(
                self.screen,
                (255, 196, 100) if ball.speed_multiplier == MASSIVE_BALL_MULTIPLIER else (138, 155, 177),
                ball.rect.center,
                max(3, inner_core),
            )

        score_panel = pygame.Rect(WIDTH // 2 - 112, 16, 224, 88)
        pygame.draw.rect(self.screen, (13, 21, 33), score_panel, border_radius=14)
        pygame.draw.rect(self.screen, (34, 48, 64), score_panel, 1, border_radius=14)
        left_text = self.font.render(str(self.left_score), True, WHITE)
        right_text = self.font.render(str(self.right_score), True, WHITE)
        self.screen.blit(left_text, left_text.get_rect(center=(WIDTH // 2 - 48, 47)))
        self.screen.blit(right_text, right_text.get_rect(center=(WIDTH // 2 + 48, 47)))
        pygame.draw.circle(self.screen, MUTED, (WIDTH // 2, 46), 2)
        if self.mode in ("bot", "players"):
            left_record = self.record_font.render(
                f"REC {self.high_scores.get(f'{self.mode}_left', 0)}",
                True,
                GOLD,
            )
            right_record = self.record_font.render(
                f"REC {self.high_scores.get(f'{self.mode}_right', 0)}",
                True,
                GOLD,
            )
            self.screen.blit(left_record, left_record.get_rect(center=(WIDTH // 2 - 62, 82)))
            self.screen.blit(right_record, right_record.get_rect(center=(WIDTH // 2 + 62, 82)))

        if self.mode == "bot":
            label_text = f"VOCÊ vs BOT {self.difficulty.upper()} | ESC para menu"
        elif self.mode == "bot_vs_bot":
            label_text = f"BOT vs BOT {self.difficulty.upper()} | ESC para menu"
        else:
            label_text = "JOGADOR 1 vs JOGADOR 2 | ESC para menu"
        label = self.record_font.render(label_text, True, MUTED)
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, HEIGHT - 24)))
        if self.admin_mode:
            power_state = {
                0.55: "LENTA",
                1.0: "NORMAL",
                MASSIVE_BALL_MULTIPLIER: "MASSIVA",
            }.get(self.ball.speed_multiplier, "NORMAL")
            powers = self.record_font.render(
                f"ADM: Q lenta | M massiva ({power_state}) | E raquete | R saque",
                True,
                CORAL if power_state == "MASSIVA" else GOLD,
            )
            self.screen.blit(powers, powers.get_rect(center=(WIDTH // 2, HEIGHT - 55)))
        if sys.platform == "android" and self.mode in ("bot", "players"):
            touch_hint = self.record_font.render(
                "TOQUE E ARRASTE EM CADA LADO PARA MOVER",
                True,
                MUTED,
            )
            self.screen.blit(
                touch_hint,
                touch_hint.get_rect(center=(WIDTH // 2, HEIGHT - 82)),
            )

        pygame.display.flip()

    def run(self) -> None:
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
                    self.handle_touch(event)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.KEYDOWN and self.admin_mode:
                    if event.key == pygame.K_q:
                        self.toggle_admin_slow()
                    elif event.key == pygame.K_e:
                        self.toggle_admin_paddle()
                    elif event.key == pygame.K_m:
                        self.toggle_admin_massive()
                    elif event.key == pygame.K_r:
                        self.ball.reset(direction=random.choice([-1, 1]))
                        self.ball_trail.clear()

            keys = pygame.key.get_pressed()

            if self.mode == "bot":
                if keys[pygame.K_w]:
                    self.left_paddle.move(-1)
                if keys[pygame.K_s]:
                    self.left_paddle.move(1)
                self.update_bot(self.right_paddle, is_left=False)
            elif self.mode == "bot_vs_bot":
                self.update_bot(self.left_paddle, is_left=True)
                self.update_bot(self.right_paddle, is_left=False)
            else:
                self.update_players()

            if self.multiball_mode:
                self._ensure_multiball_state()

            score_happened = False
            for ball in list(self.balls):
                score_left, score_right = ball.update(self.left_paddle, self.right_paddle)
                if score_left or score_right:
                    score_happened = True
                    self.left_score += score_left
                    self.right_score += score_right
                    self.ball_trail.append(ball.rect.center)
                    if len(self.ball_trail) > 12:
                        self.ball_trail.pop(0)
                    if self.multiball_mode:
                        self._ensure_multiball_state()
                        break

            if not score_happened and self.multiball_mode and len(self.balls) > 1:
                self.ball = self.balls[0]
            if score_happened:
                self._save_high_scores()

            self.draw()
            self.clock.tick(FPS)


class Menu:
    def __init__(self) -> None:
        pygame.init()
        self.screen = create_display()
        pygame.display.set_caption("Pong")
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("arial", 64, bold=True)
        self.subtitle_font = pygame.font.SysFont("arial", 19)
        self.section_font = pygame.font.SysFont("arial", 15, bold=True)
        self.option_font = pygame.font.SysFont("arial", 23, bold=True)
        self.description_font = pygame.font.SysFont("arial", 15)
        self.hint_font = pygame.font.SysFont("arial", 14)
        self.selected = 0
        self.page = "main"
        self.pending_mode = "bot"
        self.difficulty_names = list(BOT_DIFFICULTIES)
        self.pending_admin_mode = False
        self.admin_sequence = ""
        self.admin_difficulty = "Normal"
        self.admin_ball_speeds = [5, BALL_SPEED, 9]
        self.admin_ball_speed_index = 1
        self.admin_paddle_heights = [PADDLE_HEIGHT, 160, 190]
        self.admin_paddle_height_index = 0
        self.admin_multiball = False
        self.last_touch_time = -1000
        self.background = self.create_background()

    def create_background(self) -> pygame.Surface:
        background = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            amount = y / HEIGHT
            color = (
                int(BACKGROUND[0] + 8 * amount),
                int(BACKGROUND[1] + 13 * amount),
                int(BACKGROUND[2] + 19 * amount),
            )
            pygame.draw.line(background, color, (0, y), (WIDTH, y))
        return background

    def menu_options(self) -> list[tuple[str, str, str, tuple[int, int, int]]]:
        if self.page == "difficulty":
            difficulties = self.available_difficulties()
            colors = (ACCENT, BLUE, CORAL, GOLD)
            descriptions = (
                "Bot mais lento e menos preciso",
                "Um desafio equilibrado",
                "Bot rápido que prevê a trajetória",
                "Quase não deixa a bola passar",
            )
            options = [
                (name.upper(), descriptions[index], f"{index + 1:02}", colors[index])
                for index, name in enumerate(difficulties)
            ]
            options.append(("VOLTAR", "Escolher outro modo de jogo", "ESC", MUTED))
            return options
        if self.page == "admin":
            return [
                ("VOCÊ VS BOT", "Jogue com os poderes ADM", "01", ACCENT),
                ("2 JOGADORES", "Duelo local com recursos ADM", "02", BLUE),
                ("BOT VS BOT", "Assista aos bots com poderes ADM", "03", CORAL),
                ("MODO CAÓS", "Mais bolas a cada pontuação", "04", GOLD),
                ("AJUSTES", "Configurar a partida", "05", ACCENT),
                ("INFORMAÇÕES", "Detalhes do modo ADM", "06", CORAL),
                ("VOLTAR", "Menu normal", "ESC", MUTED),
            ]
        if self.page == "admin_match":
            return [
                ("VOCÊ VS BOT", "Jogue com os poderes secretos ADM", "01", ACCENT),
                ("BOT VS BOT", "Assista aos bots com os poderes ADM", "02", CORAL),
                ("VOLTAR", "Retornar ao painel ADM", "ESC", MUTED),
            ]
        if self.page == "admin_settings":
            return [
                ("DIFICULDADE", f"Bot: {self.admin_difficulty}", "01", ACCENT),
                ("VELOCIDADE DA BOLA", f"{self.admin_ball_speeds[self.admin_ball_speed_index]} px/frame", "02", BLUE),
                ("TAMANHO DA RAQUETE", f"{self.admin_paddle_heights[self.admin_paddle_height_index]} px", "03", CORAL),
                ("MODO CAÓS", "Ativado" if self.admin_multiball else "Desativado", "04", GOLD),
                ("VOLTAR", "Retornar ao painel ADM", "ESC", MUTED),
            ]
        if self.page == "admin_info":
            return []
        return [
            ("VOCÊ VS BOT", "Treine suas rebatidas contra o computador", "01", ACCENT),
            ("2 JOGADORES", "Duelo local no mesmo teclado", "02", BLUE),
            ("BOT VS BOT", "Assista a uma partida entre computadores", "03", CORAL),
            ("MODO CAÓS", "Cada ponto cria mais bolas em campo", "04", GOLD),
            ("SAIR", "Fechar o jogo", "05", MUTED),
        ]

    def available_difficulties(self) -> list[str]:
        difficulties = self.difficulty_names.copy()
        if self.pending_mode == "bot_vs_bot":
            difficulties.extend(BOT_VS_BOT_EXTRA_DIFFICULTIES)
        return difficulties

    def option_rects(self) -> list[pygame.Rect]:
        options_count = len(self.menu_options())
        if self.page == "main":
            card_width = 390
            card_height = 72
            horizontal_gap = 18
            first_x = (WIDTH - (card_width * 2 + horizontal_gap)) // 2
            first_y = 260
            rects = [
                pygame.Rect(
                    first_x + (index % 2) * (card_width + horizontal_gap),
                    first_y + (index // 2) * 82,
                    card_width,
                    card_height,
                )
                for index in range(4)
            ]
            rects.append(pygame.Rect(WIDTH // 2 - 130, 444, 260, 58))
            return rects
        if self.page == "admin":
            card_width = 390
            card_height = 66
            horizontal_gap = 18
            first_x = (WIDTH - (card_width * 2 + horizontal_gap)) // 2
            rects = [
                pygame.Rect(
                    first_x + (index % 2) * (card_width + horizontal_gap),
                    251 + (index // 2) * 76,
                    card_width,
                    card_height,
                )
                for index in range(4)
            ]
            utility_width = 248
            utility_gap = 14
            utility_x = (WIDTH - (utility_width * 3 + utility_gap * 2)) // 2
            rects.extend(
                pygame.Rect(
                    utility_x + index * (utility_width + utility_gap),
                    432,
                    utility_width,
                    62,
                )
                for index in range(3)
            )
            return rects
        if self.page == "admin_match":
            card_width = 390
            card_height = 84
            horizontal_gap = 18
            vertical_gap = 12
            rows = (options_count + 1) // 2
            total_height = rows * card_height + (rows - 1) * vertical_gap
            first_y = 228 + (290 - total_height) // 2
            first_x = (WIDTH - (card_width * 2 + horizontal_gap)) // 2
            rects = []
            for index in range(options_count):
                row = index // 2
                column = index % 2
                if index == options_count - 1 and options_count % 2:
                    x = (WIDTH - card_width) // 2
                else:
                    x = first_x + column * (card_width + horizontal_gap)
                rects.append(
                    pygame.Rect(
                        x,
                        first_y + row * (card_height + vertical_gap),
                        card_width,
                        card_height,
                    )
                )
            return rects

        card_height = 54
        card_gap = 8
        total_height = options_count * card_height + (options_count - 1) * card_gap
        first_y = 223 + (302 - total_height) // 2
        return [
            pygame.Rect(
                WIDTH // 2 - 230,
                first_y + index * (card_height + card_gap),
                460,
                card_height,
            )
            for index in range(options_count)
        ]

    def navigate_grid(self, horizontal: bool, direction: int) -> None:
        rects = self.option_rects()
        if not rects:
            return
        current = rects[self.selected]
        candidates = []
        for index, rect in enumerate(rects):
            if index == self.selected:
                continue
            dx = rect.centerx - current.centerx
            dy = rect.centery - current.centery
            primary = dx * direction if horizontal else dy * direction
            if primary > 0:
                candidates.append((abs(dy) if horizontal else abs(dx), primary, index))
        if not candidates:
            for index, rect in enumerate(rects):
                if index == self.selected:
                    continue
                dx = rect.centerx - current.centerx
                dy = rect.centery - current.centery
                primary = dx * direction if horizontal else dy * direction
                if primary < 0:
                    candidates.append((abs(dy) if horizontal else abs(dx), -primary, index))
        if candidates:
            self.selected = min(candidates)[2]

    def choose(self, index: int) -> None:
        self.selected = index
        if self.page == "difficulty":
            difficulties = self.available_difficulties()
            if index == len(difficulties):
                self.page = "admin" if self.pending_admin_mode else "main"
                self.selected = 2 if self.pending_admin_mode else 0
                return
            difficulty = difficulties[index]
            if self.pending_admin_mode:
                PongGame(
                    self.pending_mode,
                    difficulty,
                    admin_mode=True,
                    ball_speed=self.admin_ball_speeds[self.admin_ball_speed_index],
                    paddle_height=self.admin_paddle_heights[self.admin_paddle_height_index],
                    multiball_mode=self.admin_multiball,
                ).run()
            else:
                PongGame(self.pending_mode, difficulty).run()
            return
        if self.page == "admin":
            if index == 0:
                PongGame(
                    "bot",
                    self.admin_difficulty,
                    admin_mode=True,
                    ball_speed=self.admin_ball_speeds[self.admin_ball_speed_index],
                    paddle_height=self.admin_paddle_heights[self.admin_paddle_height_index],
                    multiball_mode=self.admin_multiball,
                ).run()
            elif index == 1:
                PongGame(
                    "players",
                    admin_mode=True,
                    ball_speed=self.admin_ball_speeds[self.admin_ball_speed_index],
                    paddle_height=self.admin_paddle_heights[self.admin_paddle_height_index],
                    multiball_mode=self.admin_multiball,
                ).run()
            elif index == 2:
                self.pending_mode = "bot_vs_bot"
                self.pending_admin_mode = True
                self.page = "difficulty"
                self.selected = 1
            elif index == 3:
                PongGame(
                    "bot",
                    self.admin_difficulty,
                    admin_mode=True,
                    ball_speed=self.admin_ball_speeds[self.admin_ball_speed_index],
                    paddle_height=self.admin_paddle_heights[self.admin_paddle_height_index],
                    multiball_mode=True,
                ).run()
            elif index == 4:
                self.page = "admin_settings"
                self.selected = 0
            elif index == 5:
                self.page = "admin_info"
                self.selected = 0
            else:
                self.page = "main"
                self.selected = 0
            return
        if self.page == "admin_match":
            if index in (0, 1):
                self.pending_mode = "bot" if index == 0 else "bot_vs_bot"
                if self.pending_mode == "bot_vs_bot":
                    self.pending_admin_mode = True
                    self.page = "difficulty"
                    self.selected = 1
                else:
                    self.pending_admin_mode = False
                    PongGame(
                        self.pending_mode,
                        self.admin_difficulty,
                        admin_mode=True,
                        ball_speed=self.admin_ball_speeds[self.admin_ball_speed_index],
                        paddle_height=self.admin_paddle_heights[self.admin_paddle_height_index],
                        multiball_mode=self.admin_multiball,
                    ).run()
            else:
                self.page = "admin"
                self.selected = 1
            return
        if self.page == "admin_settings":
            self.change_admin_setting(index)
            return

        if self.page == "admin_info":
            self.page = "admin"
            self.selected = 4
            return

        if self.page == "main":
            if index == 0 or index == 2:
                self.pending_mode = "bot" if index == 0 else "bot_vs_bot"
                self.pending_admin_mode = False
                self.page = "difficulty"
                self.selected = 1
            elif index == 1:
                PongGame("players").run()
            elif index == 3:
                PongGame("bot", multiball_mode=True).run()
            else:
                pygame.quit()
                sys.exit()

    def change_admin_setting(self, index: int, direction: int = 1) -> None:
        if index == 0:
            current = self.difficulty_names.index(self.admin_difficulty)
            self.admin_difficulty = self.difficulty_names[
                (current + direction) % len(self.difficulty_names)
            ]
        elif index == 1:
            self.admin_ball_speed_index = (
                self.admin_ball_speed_index + direction
            ) % len(self.admin_ball_speeds)
        elif index == 2:
            self.admin_paddle_height_index = (
                self.admin_paddle_height_index + direction
            ) % len(self.admin_paddle_heights)
        elif index == 3:
            self.admin_multiball = not self.admin_multiball
        else:
            self.page = "admin"
            self.selected = 0

    def draw(self) -> None:
        self.screen.blit(self.background, (0, 0))

        title = self.title_font.render("PONG", True, WHITE)
        title_rect = title.get_rect(center=(WIDTH // 2, 112))
        self.screen.blit(title, title_rect)
        pygame.draw.rect(
            self.screen,
            ACCENT,
            (WIDTH // 2 - 22, title_rect.bottom + 5, 44, 2),
            border_radius=1,
        )
        subtitle_text = (
            "ESCOLHA A DIFICULDADE"
            if self.page == "difficulty"
            else {
                "main": "ESCOLHA UM MODO DE JOGO",
                "admin": "PAINEL SECRETO DE ADMINISTRADOR",
                "admin_match": "ESCOLHA O MODO DA PARTIDA ADM",
                "admin_settings": "CONFIGURAÇÕES AVANÇADAS",
                "admin_info": "INFORMAÇÕES DO MODO SECRETO",
            }.get(self.page, "ESCOLHA SEU MODO DE JOGO")
        )
        subtitle = self.subtitle_font.render(subtitle_text, True, MUTED)
        self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 207)))
        pygame.draw.line(self.screen, (39, 51, 67), (70, 224), (WIDTH - 70, 224), 1)

        if self.page in ("main", "admin"):
            heading = self.section_font.render("JOGAR  —  MODOS", True, ACCENT)
            self.screen.blit(heading, (70, 234))
            if self.page == "admin":
                tools_heading = self.section_font.render(
                    "FERRAMENTAS ADM", True, GOLD
                )
                self.screen.blit(tools_heading, (70, 409))

        options = self.menu_options()
        for index, ((title_text, description, number, accent), rect) in enumerate(
            zip(options, self.option_rects())
        ):
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            active = index == self.selected or hovered
            if hovered:
                self.selected = index
            fill = (24, 35, 49) if active else (16, 25, 38)
            border = accent if active else (31, 44, 59)
            pygame.draw.rect(self.screen, fill, rect, border_radius=8)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=8)
            if active:
                pygame.draw.rect(
                    self.screen,
                    accent,
                    (rect.left, rect.top + 10, 3, rect.height - 20),
                    border_radius=1,
                )

            number_surface = self.description_font.render(number, True, accent if active else MUTED)
            self.screen.blit(number_surface, number_surface.get_rect(center=(rect.left + 34, rect.centery)))

            option_surface = self.option_font.render(
                title_text, True, WHITE if active else (211, 219, 229)
            )
            text_offset = (rect.height - 53) // 2
            self.screen.blit(option_surface, (rect.left + 68, rect.top + text_offset))
            description_surface = self.description_font.render(description, True, MUTED)
            self.screen.blit(
                description_surface,
                (rect.left + 69, rect.top + text_offset + 29),
            )

        hint = self.hint_font.render(
            (
                (
                    "ESC OU ENTER PARA VOLTAR AO PAINEL ADM"
                    if self.page == "admin_info"
                    else (
                        "USE  ↑  ↓  ←  →  PARA NAVEGAR     ENTER PARA CONFIRMAR"
                        if self.page in ("main", "admin")
                        else "USE  ↑  ↓  PARA ESCOLHER     ENTER PARA CONFIRMAR     ESC PARA VOLTAR"
                    )
                )
                if self.page != "main"
                else "USE  ↑  ↓  ←  →  PARA NAVEGAR     ENTER OU CLIQUE PARA SELECIONAR"
            ),
            True,
            MUTED,
        )
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 42)))
        if self.page == "admin_info":
            panel = pygame.Rect(165, 245, 570, 225)
            pygame.draw.rect(self.screen, PANEL, panel, border_radius=16)
            pygame.draw.rect(self.screen, CORAL, panel, 2, border_radius=16)
            details = [
                ("MODO ADM", "Recursos secretos para partidas locais."),
                ("Q / M", "Bola lenta / velocidade massiva (6x)."),
                ("E / R", "Raquete maior / reinicia o saque."),
                ("RASTRO", "A bola massiva ganha efeito visual."),
                ("VOLTAR", "ESC ou ENTER retorna ao painel ADM."),
            ]
            for index, (label, detail) in enumerate(details):
                y = panel.top + 20 + index * 38
                self.screen.blit(
                    self.option_font.render(label, True, CORAL if index < 2 else ACCENT),
                    (panel.left + 22, y),
                )
                self.screen.blit(
                    self.description_font.render(detail, True, PALE),
                    (panel.left + 195, y + 7),
                )

    def run(self) -> None:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if self.page == "admin_info":
                        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                            self.page = "admin"
                            self.selected = 5
                        continue

                    if self.page in ("main", "admin") and event.unicode:
                        self.admin_sequence = (self.admin_sequence + event.unicode.lower())[-3:]
                        if self.admin_sequence == "adm":
                            self.page = "admin"
                            self.selected = 0
                            self.admin_sequence = ""
                            continue

                    if (
                        self.page in ("main", "admin", "admin_match")
                        and event.key in (pygame.K_LEFT, pygame.K_RIGHT)
                    ):
                        self.navigate_grid(
                            horizontal=True,
                            direction=-1 if event.key == pygame.K_LEFT else 1,
                        )
                    elif (
                        self.page in ("main", "admin", "admin_match")
                        and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s)
                    ):
                        self.navigate_grid(
                            horizontal=False,
                            direction=-1 if event.key in (pygame.K_UP, pygame.K_w) else 1,
                        )
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.selected = (self.selected - 1) % len(self.menu_options())
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.selected = (self.selected + 1) % len(self.menu_options())
                    elif (
                        self.page == "admin_settings"
                        and self.selected < 3
                        and event.key in (pygame.K_LEFT, pygame.K_RIGHT)
                    ):
                        self.change_admin_setting(
                            self.selected,
                            -1 if event.key == pygame.K_LEFT else 1,
                        )
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.choose(self.selected)
                    elif event.key == pygame.K_ESCAPE:
                        if self.page == "difficulty":
                            self.page = "admin" if self.pending_admin_mode else "main"
                            self.selected = 2 if self.pending_admin_mode else 0
                        elif self.page == "admin_settings":
                            self.page = "admin"
                            self.selected = 4
                        elif self.page == "admin_match":
                            self.page = "admin"
                            self.selected = 1
                        elif self.page == "admin":
                            self.page = "main"
                            self.selected = 0
                        else:
                            pygame.quit()
                            sys.exit()

                if event.type == pygame.MOUSEMOTION:
                    for index, rect in enumerate(self.option_rects()):
                        if rect.collidepoint(event.pos):
                            self.selected = index
                            break
                elif event.type == pygame.FINGERDOWN:
                    self.last_touch_time = pygame.time.get_ticks()
                    position = (round(event.x * WIDTH), round(event.y * HEIGHT))
                    for index, rect in enumerate(self.option_rects()):
                        if rect.collidepoint(position):
                            self.choose(index)
                            break
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if pygame.time.get_ticks() - self.last_touch_time < 400:
                        continue
                    for index, rect in enumerate(self.option_rects()):
                        if rect.collidepoint(event.pos):
                            self.choose(index)
                            break

            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Menu().run()