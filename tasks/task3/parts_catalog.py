"""Lexical (TF-IDF + cosine similarity) search over the parts catalog.

See backend/task3/findings.md and descriptiveanalysis.ipynb for the rationale:
short, templated technical descriptions favor exact keyword matching over
embeddings, which would blur precise numeric ratings together.
"""

import io
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TOKEN_PATTERN = r"(?u)\b\w[\w.]*\b"

ID_COLUMN = "ID"
DESCRIPTION_COLUMN = "DESCRIPTION"
CURRENT_COLUMN = "Rated Current (A)"
CURRENT_CLEANED_COLUMN = "Rated Current (A) - cleaned"

_LEADING_NUMBER = re.compile(r"[\d.]+")


def _clean_current(value):
    """"1.6A" -> 1.6; anything unparseable (including missing) -> NaN."""
    if pd.isna(value):
        return float("nan")
    match = _LEADING_NUMBER.match(str(value).strip())
    if not match:
        return float("nan")
    try:
        return float(match.group())
    except ValueError:
        return float("nan")


class PartsCatalog:
    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self._build()

    def _build(self) -> None:
        if CURRENT_COLUMN in self.df.columns:
            self.df[CURRENT_CLEANED_COLUMN] = self.df[CURRENT_COLUMN].apply(_clean_current)
        else:
            self.df[CURRENT_CLEANED_COLUMN] = float("nan")

        known_mask = self.df[DESCRIPTION_COLUMN].notna()
        self._known_df = self.df[known_mask].reset_index(drop=True)

        # Only rows with a DESCRIPTION are searchable/known, per the data:
        # a missing description means there's nothing to match alternatives on.
        self._id_lookup = {
            str(part_id).upper(): str(part_id) for part_id in self._known_df[ID_COLUMN]
        }
        self._id_to_pos = {
            str(part_id): pos for pos, part_id in enumerate(self._known_df[ID_COLUMN])
        }

        descriptions = self._known_df[DESCRIPTION_COLUMN].astype(str).tolist()
        if descriptions:
            self._vectorizer = TfidfVectorizer(token_pattern=TOKEN_PATTERN)
            self._matrix = self._vectorizer.fit_transform(descriptions)
        else:
            self._vectorizer = None
            self._matrix = None

    @classmethod
    def from_csv(cls, path) -> "PartsCatalog":
        return cls(pd.read_csv(path, sep=";"))

    def known_ids(self) -> set:
        return set(self._id_lookup.values())

    def _resolve_id(self, part_id):
        return self._id_lookup.get(str(part_id).upper())

    def find_alternatives(self, part_id, k: int = 5) -> dict:
        resolved_id = self._resolve_id(part_id)
        if resolved_id is None:
            return {
                "query_id": str(part_id),
                "alternatives": [],
                "warnings": [f"Part '{part_id}' was not found in the catalog."],
            }

        warnings = []
        query_pos = self._id_to_pos[resolved_id]
        query_current = self._known_df.loc[query_pos, CURRENT_CLEANED_COLUMN]
        filter_by_current = pd.notna(query_current)
        if not filter_by_current:
            warnings.append(
                f"Rated Current is missing for '{resolved_id}'; alternatives below are "
                "unverified by rated current match."
            )

        similarities = cosine_similarity(self._matrix[query_pos], self._matrix)[0]

        candidates = []
        for pos, part_id_value in enumerate(self._known_df[ID_COLUMN]):
            if pos == query_pos:
                continue
            if filter_by_current:
                candidate_current = self._known_df.loc[pos, CURRENT_CLEANED_COLUMN]
                if pd.isna(candidate_current) or candidate_current != query_current:
                    continue
            candidates.append((similarities[pos], pos, str(part_id_value)))

        candidates.sort(key=lambda item: item[0], reverse=True)

        alternatives = [
            {
                "id": part_id_value,
                "score": float(score),
                "description": self._known_df.loc[pos, DESCRIPTION_COLUMN],
            }
            for score, pos, part_id_value in candidates[:k]
        ]

        return {"query_id": resolved_id, "alternatives": alternatives, "warnings": warnings}

    def search_by_text(self, text: str, k: int = 5) -> dict:
        if self._vectorizer is None:
            return {"query": text, "matches": []}

        query_vector = self._vectorizer.transform([text])
        similarities = cosine_similarity(query_vector, self._matrix)[0]
        ranked = sorted(enumerate(similarities), key=lambda item: item[1], reverse=True)[:k]

        matches = [
            {
                "id": str(self._known_df.loc[pos, ID_COLUMN]),
                "score": float(score),
                "description": self._known_df.loc[pos, DESCRIPTION_COLUMN],
            }
            for pos, score in ranked
        ]
        return {"query": text, "matches": matches}

    def add_csv_text(self, csv_text: str, source_label: str = "uploaded") -> int:
        new_df = pd.read_csv(io.StringIO(csv_text), sep=";")
        if DESCRIPTION_COLUMN not in new_df.columns:
            raise ValueError(f"CSV is missing a required '{DESCRIPTION_COLUMN}' column.")

        existing_ids = set(self.df[ID_COLUMN].astype(str))
        new_df = new_df.copy()
        new_df[ID_COLUMN] = new_df[ID_COLUMN].astype(str)
        new_df[ID_COLUMN] = new_df[ID_COLUMN].apply(
            lambda part_id: f"{source_label}_{part_id}" if part_id in existing_ids else part_id
        )

        self.df = pd.concat([self.df, new_df], ignore_index=True)
        self._build()
        return len(new_df)

    def copy(self) -> "PartsCatalog":
        return PartsCatalog(self.df.copy())
