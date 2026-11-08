"""A tee: a course and tee as Trackman lists them, with its numbers and R13's bounds on them."""

from dataclasses import dataclass

HOLES = 18
MIN_PAR = 3
MAX_PAR = 6
MIN_SLOPE = 55
MAX_SLOPE = 155
MIN_RATING_TENTHS = 500
MAX_RATING_TENTHS = 900


def _check_rating_and_slope(course_rating_tenths: int, slope: int) -> None:
    """R13: the owner's bound on a course rating, and WHS's slope range."""
    if not MIN_RATING_TENTHS <= course_rating_tenths <= MAX_RATING_TENTHS:
        raise ValueError("a course rating is 50.0 to 90.0")
    if not MIN_SLOPE <= slope <= MAX_SLOPE:
        raise ValueError(f"a slope is {MIN_SLOPE} to {MAX_SLOPE}")


@dataclass(frozen=True)
class Tee:
    """A course and tee as Trackman lists them, which together identify the tee, and its numbers."""

    course: str
    name: str
    pars: tuple[int, ...]
    stroke_indexes: tuple[int, ...]
    course_rating_tenths: int
    slope: int

    def __post_init__(self) -> None:
        if not self.course:
            raise ValueError("a tee has a course name")
        if not self.name:
            raise ValueError("a tee has a tee name")
        if len(self.pars) != HOLES:
            raise ValueError(f"a tee has {HOLES} pars, got {len(self.pars)}")
        if any(par < MIN_PAR or par > MAX_PAR for par in self.pars):
            raise ValueError(f"every par is {MIN_PAR} to {MAX_PAR}")
        if len(self.stroke_indexes) != HOLES:
            raise ValueError(f"a tee has {HOLES} stroke indexes, got {len(self.stroke_indexes)}")
        if sorted(self.stroke_indexes) != list(range(1, HOLES + 1)):
            raise ValueError(f"stroke indexes are 1 to {HOLES}, once each")
        _check_rating_and_slope(self.course_rating_tenths, self.slope)

    @property
    def par_total(self) -> int:
        return sum(self.pars)
