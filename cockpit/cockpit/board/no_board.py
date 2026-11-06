from cockpit.board.board import Board
from cockpit.board.board_state import BoardState
from cockpit.not_used import NotUsed


class NoBoard(Board):
    def read(self) -> BoardState:
        raise NotUsed("this project keeps no board (no paths.board_dir in .cockpit.json)")
