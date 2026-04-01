import random


def shuffle_question(question_row):
    options = [
        (0, question_row["option_a"]),
        (1, question_row["option_b"]),
        (2, question_row["option_c"]),
        (3, question_row["option_d"]),
    ]

    correct_index = int(question_row["correct_option"]) - 1

    random.shuffle(options)

    new_correct_index = next(
        i for i, (original_index, _) in enumerate(options)
        if original_index == correct_index
    )

    shuffled_options = [text for _, text in options]

    return shuffled_options, new_correct_index