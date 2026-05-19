import logging

logger = logging.getLogger(__name__)


def distill_knowledge(teacher_model: str, student_model: str):
    logger.info(f"Starting distillation from {teacher_model} to {student_model}")
    return True


if __name__ == "__main__":
    distill_knowledge("llama-70b", "sovereign-1b")
