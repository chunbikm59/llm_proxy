#!/usr/bin/env python3
"""
Test OpenAI Embedding API
"""

from openai import OpenAI

# Shared configuration
API_KEY = ''
BASE_URL = 'http://127.0.0.1:1235'
MODEL = "text-embedding-bge-m3@fp16"


def test_embedding():
    """Test creating embeddings with OpenAI API"""

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # Test text samples
    test_texts = [
        "The quick brown fox jumps over the lazy dog",
        "Python is a great programming language",
        "Machine learning and AI are transforming technology",
        "I love building APIs with FastAPI",
    ]

    print("Testing OpenAI Embedding API\n")
    print(f"Processing {len(test_texts)} text samples...\n")

    # Create embeddings
    response = client.embeddings.create(
        model=MODEL,
        input=test_texts
    )

    # Display results
    for idx, embedding_data in enumerate(response.data):
        text = test_texts[idx]
        vector = embedding_data.embedding

        print(f"Text {idx + 1}: {text}")
        print(f"  - Embedding dimension: {len(vector)}")
        print(f"  - First 5 values: {vector[:5]}")
        print(f"  - Vector norm: {sum(x**2 for x in vector)**0.5:.4f}")
        print()

    # Display token usage
    print(f"Token usage:")
    print(f"  - Prompt tokens: {response.usage.prompt_tokens}")
    print(f"  - Total tokens: {response.usage.total_tokens}")
    print()

    # Test similarity between embeddings
    print("Cosine similarity between embeddings:")
    embeddings = [data.embedding for data in response.data]

    # Calculate similarity between first and other embeddings
    def cosine_similarity(vec1, vec2):
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(x**2 for x in vec1)**0.5
        norm2 = sum(x**2 for x in vec2)**0.5
        return dot_product / (norm1 * norm2)

    base_text = test_texts[0]
    print(f"\nSimilarity with '{base_text}':")

    for idx in range(1, len(test_texts)):
        similarity = cosine_similarity(embeddings[0], embeddings[idx])
        print(f"  - vs '{test_texts[idx]}': {similarity:.4f}")


def test_single_text():
    """Test embedding a single text"""

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    text = "Hello, this is a test embedding"
    print(f"\nTesting single text embedding:")
    print(f"Text: {text}")

    response = client.embeddings.create(
        model=MODEL,
        input=text
    )

    embedding = response.data[0].embedding
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 10 values: {embedding[:10]}")


if __name__ == "__main__":
    test_embedding()
    test_single_text()
