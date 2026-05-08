import re
from collections import Counter
from typing import Dict, List

import numpy as np


class SLMDataPipeline:
    '''
    Small Language Model (SLM) Data pre-processor.
    Ingests raw Telegram/Twitter financial text, tokenizes, removes stop words,
    and converts to TF-IDF vectors for fast sentiment inference.
    '''
    def __init__(self):
        self.vocab = {}
        self.idf = {}
        self.stop_words = {"the", "is", "at", "which", "on", "and", "a", "of", "to", "in", "for"}
        self.doc_count = 0

    def clean_text(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r'http\S+', '', text) # Remove URLs
        text = re.sub(r'[^a-z0-9\s]', '', text) # Remove punctuation
        tokens = text.split()
        return [t for t in tokens if t not in self.stop_words]

    def fit(self, documents: List[str]):
        '''Builds the vocabulary and Inverse Document Frequency (IDF) mapping.'''
        self.doc_count = len(documents)
        df = Counter()

        for doc in documents:
            tokens = set(self.clean_text(doc))
            for t in tokens:
                df[t] += 1

        for word, count in df.items():
            self.vocab[word] = len(self.vocab)
            # IDF = log(N / DF)
            self.idf[word] = np.log(self.doc_count / (count + 1.0))

    def transform(self, text: str) -> np.ndarray:
        '''Converts text into a TF-IDF sparse vector.'''
        vector = np.zeros(len(self.vocab))
        if not self.vocab:
            return vector

        tokens = self.clean_text(text)
        tf = Counter(tokens)

        total_terms = len(tokens) if tokens else 1
        for word, count in tf.items():
            if word in self.vocab:
                idx = self.vocab[word]
                term_frequency = count / total_terms
                vector[idx] = term_frequency * self.idf[word]

        return vector
