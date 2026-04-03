from schemas.schemas import Chapter, Section

def parse_book():
    sections = [
        Section("1.1", "Intro", "Intro content"),
        Section("1.2", "Basics", "Basics content"),
    ]

    chapter = Chapter(
        "1",
        "Sample Chapter",
        "Full chapter content",
        sections
    )

    return [chapter]