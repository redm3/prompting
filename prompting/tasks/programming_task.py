from typing import ClassVar
from prompting.datasets.huggingface_github import (
    HuggingFaceGithubDatasetEntry,
    MIN_INPUT_LINES,
    OUTPUT_LINES,
)
from prompting.tasks.base_task import BaseTextTask
from prompting.rewards.reward import BaseRewardConfig, BaseRewardModel
from prompting.rewards.rouge import RougeRewardModel
from prompting.rewards.relevance import RelevanceRewardModel
from prompting.utils.cleaners import CleanerPipeline
import textwrap
from prompting.llms.apis.gpt_wrapper import openai_client, LLMMessage, LLMMessages


class ProgrammingRewardConfig(BaseRewardConfig):
    reward_definitions: ClassVar[list[BaseRewardModel]] = [
        RougeRewardModel(weight=0.5),
        RelevanceRewardModel(weight=0.5),
    ]


CODE_MODIFICATION_PROMPT = textwrap.dedent(
    """You are an agent that takes in some code and modifies it by changing ALL variable, function names etc. as well as other
    information such as comments, docstrings, etc. to make it look like it was written by a different person. Also shuffle around the import statements.
    Make sure to keep the code functional and the logic intact.
    It should not be identifiable as the original code though without analysing it's functionality.


    Original code:
    {file_content}

    Respond only with the new and modified code! Make sure to respond with the entire code, not just a part of it.
    """
)


class ProgrammingTask(BaseTextTask):
    name: ClassVar[str] = "programming"
    cleaning_pipeline: ClassVar[CleanerPipeline] = CleanerPipeline()
    query: str | None = None
    reference: str | None = None

    def make_query(self, dataset_entry: HuggingFaceGithubDatasetEntry):
        response, _ = openai_client.chat_complete(
            messages=LLMMessages(
                [LLMMessage(content=CODE_MODIFICATION_PROMPT.format(file_content=dataset_entry.file_content))]
            )
        )
        modified_code = response.choices[0].message.content
        if len(modified_code.split("\n")) < MIN_INPUT_LINES + OUTPUT_LINES:
            return
        line_cutoff = max(MIN_INPUT_LINES, len(modified_code.split("\n")) - OUTPUT_LINES)
        self.query = "\n".join(modified_code.split("\n")[:line_cutoff])
        self.reference = "\n".join(modified_code.split("\n")[line_cutoff : line_cutoff + OUTPUT_LINES])
        return self.query
