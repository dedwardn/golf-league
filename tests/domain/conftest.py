from league.domain.facts import Tee

PARS = (4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5)
STROKE_INDEXES = (1, 11, 15, 5, 3, 9, 17, 7, 13, 2, 12, 16, 6, 4, 10, 18, 8, 14)

# Par 72, rating 73.2, slope 131: the tee of the R1 worked example.
TEE = Tee(PARS, STROKE_INDEXES, course_rating_tenths=732, slope=131)
