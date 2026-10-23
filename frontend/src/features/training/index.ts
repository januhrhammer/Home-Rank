// The feature's public surface: other parts of the app import from here, not from its files.
export { boardMove, legalDests, squaresOf, turnOf, typedMove } from "./puzzle";
export { Ratings } from "./PuzzlePlayer";
export { type Rating, type Review, useChangeRating } from "./training";
export { TrainPage } from "./TrainPage";
