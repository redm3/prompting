import time

import bittensor as bt

from transformers import Pipeline, pipeline
from prompting.mock import MockPipeline


def load_pipeline(model_id, device=None, torch_dtype=None, mock=False):
    """Loads the HuggingFace pipeline for the LLM, or a mock pipeline if mock=True"""
    
    if mock or model_id == 'mock':
        return MockPipeline(model_id)
    
    if not device.startswith("cuda"):
        bt.logging.warning("Only crazy people run this on CPU. It is not recommended.")

    return pipeline(
        "text-generation",
        model=model_id,
        device=device,
        torch_dtype=torch_dtype,
    )


class HuggingFaceLLM:
    def __init__(
        self,
        llm_pipeline: Pipeline,
        system_prompt,
        max_new_tokens=256,
        do_sample=True,
        temperature=0.7,
        top_k=50,
        top_p=0.95,
    ):
        self.llm_pipeline = llm_pipeline
        self.system_prompt = system_prompt
        self.kwargs = dict(
            do_sample=do_sample,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            max_new_tokens=max_new_tokens,
        )

        self.messages = [{"content": self.system_prompt, "role": "system"}]
        self.times = [0]

    def query(
        self, message, cleanup=True, role="user", disregard_system_prompt=False
    ):
        messages = self.messages + [{"content": message, "role": role}]

        if disregard_system_prompt:
            messages = messages[1:]

        tbeg = time.time()
        response = self.forward(messages, cleanup=cleanup)

        self.messages = messages + [{"content": response, "role": "assistant"}]
        self.times = self.times + [0, time.time() - tbeg]
        return response

    def __call__(self, messages):
        return self.forward(messages)

    def _make_prompt(self, messages):
        return self.llm_pipeline.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def forward(self, messages, cleanup=False, preformat_messages=False):
        prompt = self._make_prompt(messages)
        outputs = self.llm_pipeline(prompt, **self.kwargs)
        response = outputs[0]["generated_text"]

        response = response.replace(prompt, "").strip()
        if cleanup and response.startswith("Assistant:"):
            response = (
                response.strip("Assistant:").split("User:")[0].strip("\n")
            )
            # Prune unfinished sentences
            if not response.endswith("."):
                bt.logging.debug("Pruning unfinished sentence.")
                response = response[: response.rfind(".")]+'.'

        bt.logging.info(f"{self.__class__.__name__} generated the following output:\n{response}")
        return response