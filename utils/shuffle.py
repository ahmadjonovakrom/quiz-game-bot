import random

def shuffle_question(question_row):
    options = [
        ("a", question_row["option_a"]),
        ("b", question_row["option_b"]),
        ("c", question_row["option_c"]),
        ("d", question_row["option_d"]),
    ]

    correct_key = question_row["correct_option"]

    # Shuffle options
    random.shuffle(options)

    # Find new correct index
    new_correct_index = next(
        i for i, (key, _) in enumerate(options) if key == correct_key
    )

    # Extract shuffled text only
    shuffled_options = [text for _, text in options]

    return shuffled_options, new_correct_index