from pydantic import model_validator, ConfigDict
from prompting.datasets.base import DatasetEntry, BaseDataset
from datasets import load_dataset
from loguru import logger

ALLOWED_FILE_ENDINGS = {
    "python": [".py"],
    "js": [".js", ".jsx", ".ts", ".tsx"],
}
MIN_FILE_SIZE = 100
MAX_FILE_SIZE = 100_000
MIN_INPUT_LINES = 10
OUTPUT_LINES = 10
MAX_LINES = 500
RETRIES = 50  # Increased retry limit


class HuggingFaceGithubDatasetEntry(DatasetEntry):
    github_url: str
    file_path: str
    file_content: str


class HuggingFaceGithubDataset(BaseDataset):
    language: str = "python"
    dataset: any = None
    iterator: any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def load_dataset(self) -> "HuggingFaceGithubDataset":
        self.dataset = load_dataset("codeparrot/github-code", streaming=True, split="train")
        self.iterator = iter(self.dataset.filter(self._filter_function))
        return self

    def _filter_function(self, example):
        return (
            example["language"].lower() == self.language.lower()
            and any(example["path"].endswith(ending) for ending in ALLOWED_FILE_ENDINGS[self.language])
            and MIN_FILE_SIZE <= example["size"] <= MAX_FILE_SIZE
            and len(example["code"].split("\n")) >= (MIN_INPUT_LINES + OUTPUT_LINES)
        )

    def _process_entry(self, entry: dict) -> HuggingFaceGithubDatasetEntry:
        file_content = "\n".join(entry["code"].split("\n")[:MAX_LINES])
        return HuggingFaceGithubDatasetEntry(
            github_url=f"https://github.com/{entry['repo_name']}", file_path=entry["path"], file_content=file_content
        )

    def get(self) -> HuggingFaceGithubDatasetEntry:
        return self.next()

    def next(self) -> HuggingFaceGithubDatasetEntry:
        for _ in range(RETRIES):
            try:
                entry = next(self.iterator)
                return self._process_entry(entry)
            except StopIteration:
                logger.warning("Reached end of dataset. Resetting iterator.")
                self.reset()
            except Exception as ex:
                logger.error(f"Error processing entry: {ex}")
        raise Exception("Failed to get a valid file after multiple attempts")

    def random(self) -> HuggingFaceGithubDatasetEntry:
        # Note: The dataset is streamed, so true random access is not possible.
        # This method will just return the next item, similar to `next()`.
        return self.next()

    def reset(self):
        self.iterator = iter(self.dataset.filter(self._filter_function))