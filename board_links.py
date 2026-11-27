"""Conservative board-profile resolution for generated navigation (not hardware evidence)."""
from collections import defaultdict
import re
from urllib.parse import quote

BOARD_KINDS = {'board', 'board_feature', 'board_candidate', 'board_change'}


def profile_url(board):
    return 'boards/' + quote(board['slug'], safe='') + '.html'


class BoardLinks:
    def __init__(self, boards):
        self.boards = boards
        self.aliases = defaultdict(set)
        for key, board in boards.items():
            for name in [board.get('name'), board.get('folder'), board.get('full_name'), *board.get('targets', [])]:
                if name:
                    self.aliases[str(name).casefold()].add(key)

    def resolve(self, event, associated=()):
        """Return one exact profile or None; never choose an ambiguous board."""
        subject = str(event.get('subject', '')).strip().casefold()
        matches = self.aliases.get(subject, set())
        associated = set(associated)
        scoped = matches & associated
        if len(scoped) == 1:
            return next(iter(scoped))
        if len(scoped) > 1:
            return None
        if event.get('kind') in BOARD_KINDS and not associated and len(matches) == 1:
            return next(iter(matches))
        return None

    def proposal(self, title):
        """Link explicit identifiers in board-scoped PR titles, not speculative matches."""
        if not re.match(r'^boards?\s*:', title, re.I):
            return []
        matches = set()
        for token in re.findall(r'[\w/-]+', title.casefold()):
            keys = self.aliases.get(token, set())
            if len(keys) == 1:
                matches.update(keys)
        return sorted(matches)
