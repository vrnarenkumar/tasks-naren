# Task 3 — Findings

`Parts.csv` has 998 rows and 32 columns. Only 663 rows (66.4%) have a DESCRIPTION.

## Finding 1: Missing data is tied to the type of part, not random

Grouping parts by their type (Indicator, Surface mount, Thru-Hole, etc.) and checking how often the `Height` field is filled shows big differences between groups — some types have it filled 100% of the time, others 0%. If the missing data was random, every group would look about the same. It doesn't, so the type of part decides what gets recorded, not chance.

## Finding 2: A missing description is a warning sign for the whole row

Rows that have a DESCRIPTION are 77.3% filled on average across all the other columns. Rows without a DESCRIPTION drop to 32%. So if a row is missing its description, the rest of the row is probably missing a lot too.

## Finding 3: But "missing description" does not mean "missing everything"

Looking only at rows with no DESCRIPTION, how filled each column is varies a lot. Some columns like Size (68%) and Application (61%) are still mostly there. Others like Pre-arcing time (1%) and Rated Voltage (10%) are almost completely empty. So you can't just throw away every row that's missing a description — you have to check column by column.

## Difficulty: numbers are stored as text with the unit attached

Fields like `Rated Current (A)` hold values like `"1.6A"` instead of the number `1.6`. This means you can't do basic math on them — trying `.mean()` on this column fails with an error, because the whole column is treated as words, not numbers.

**How I handled it:** for each value, remove the last character (the unit letter) and turn what's left into a number. For example `"1.6A"` becomes `1.6`. This same problem shows up in many other columns too (Voltage, Height, Temperature, Pre-arcing time), since almost every measured value in this dataset has its unit written directly into the text.

One thing worth noting: even after cleaning, current ratings aren't smoothly spread out — they cluster around a small set of standard values (1A, 1.5A, 2A, 2.5A, 3A, 5A, 6.3A, 8A, 10A, 12.5A...), because fuses are only made in specific standard sizes. So an average current value isn't very meaningful on its own — no part is actually rated at the average.

## Finding 5 alternative parts, based on DESCRIPTION

**The problem:** for each part, find 5 other parts that could act as a substitute, using only the free-text DESCRIPTION field.

**The approach — two steps:**

1. Turn every DESCRIPTION into a list of numbers (a "vector") using TF-IDF, so two descriptions can be compared mathematically. Common words like "Indicator" get a low weight since almost every part has them; rare, specific words (like an exact current rating) get a high weight, since they're what actually tells two parts apart.
2. Compare every part's vector to every other part's vector (cosine similarity) to get a similarity score between 0 and 1, then take the 5 highest-scoring matches.

This is a **lexical search** approach — matching parts based on the actual words/tokens they share, rather than a "semantic" approach (embeddings), which tries to match based on meaning instead of exact wording. **I've used lexical search before in a project at Ford, which is part of why I reached for it here as a proven, explainable starting point.** Combined with the Rated Current filter below, the overall method is: filter on a structured attribute first, then rank the remaining candidates with lexical search.

**Why TF-IDF, and not something fancier (embeddings/semantic search)?**
- The descriptions are short, templated technical text (not natural sentences), so plain keyword matching is a good fit.
- It runs instantly with no model download or GPU, and is fully explainable — you can see exactly which words caused a match.
- Precise numbers (like an exact current rating) are what matters most here, and keyword-based methods keep exact numbers distinct. Meaning-based methods (embeddings) tend to blur close numbers together, which is the wrong behaviour for this data.
- FAISS (a tool for speeding up similarity search) was considered and intentionally not used — it's built for searching millions of vectors quickly by approximating the answer. With under 700 descriptions, comparing everything directly is already exact and near-instant, so FAISS would only add complexity with no real benefit here.