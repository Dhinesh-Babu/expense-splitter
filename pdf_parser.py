import os
import json
import pathlib
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List


# Pydantic model for strctured output using Google Gemini API
class Item(BaseModel):
    name: str = Field(description="The full name of the purchased item.")
    status: str = Field(
        description="The shopping status, e.g., 'Shopped', 'Weight adjusted', or 'Substituted'."
    )
    quantity: int = Field(description="The quantity of the item purchased.")
    cost: float = Field(description="The total price for that line item.")


# New model specifically for the list of items - this is necessary to match the expected schema
# Output is not accurately represented by a single Item model, so we use a list wrapper.
# TODO: Figure out how to use the `List` type directly in the model definition.
class ItemsList(BaseModel):
    items: List[Item]


# Summary model
# NOTE: This model is used to extract the summary details from the receipt. Making it a single API call does not work well, so we use a separate model for the summary.


class Summary(BaseModel):
    subtotal: float = Field(
        description="The subtotal of all items before taxes and tips."
    )
    tax: float = Field(description="The total tax amount.")
    tip: float = Field(
        description="The driver tip amount. Should be 0.0 if not present."
    )
    total: float = Field(description="The final grand total of the bill.")


def parse_walmart_pdf(filepath):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)

        # 1. Upload the PDF file once to be used by both API calls.
        print("Uploading file to Gemini API...")
        uploaded_file = genai.upload_file(path=filepath, display_name="Walmart Receipt")
        print(f"File uploaded successfully: {uploaded_file.uri}")

        # --- FIRST API CALL: Extract Line Items ---
        print("Making API call for line items...")

        items_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ItemsList,
            },
        )

        items_prompt = """
        You are an expert receipt processing agent. Your task is to analyze the provided PDF document of a Walmart receipt.

        The receipt has a two-column layout. The item's full name is on the left side of the page, and its corresponding details (status, quantity, and cost) are on the far right side of the same horizontal line.
        For each line item, extract the following details:
        - The full name of the item (everything before the dots).
        - The shopping status (which can be "Shopped", "Weight adjusted", or "Substituted").
        - The quantity purchased (always a whole number followed by "Qty").
        - The cost of the item (a decimal number that follows a dollar sign '$').
        Ensure you extract these details accurately, even if the format varies slightly.


        Now, process the entire attached document and extract ONLY the individual purchased line items. Do not include summary details like subtotal, tax, or total in this response.
        """

        items_response = items_model.generate_content([items_prompt, uploaded_file])

        items_result_object = items_response.candidates[0].content.parts[0].text
        print("items_result_object:", items_result_object)
        items_data = ItemsList.model_validate_json(items_result_object)
        items_list = [item.model_dump() for item in items_data.items]

        # --- SECOND API CALL: Extract Summary ---
        print("Making API call for summary details...")

        summary_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": Summary,
            },
        )

        summary_prompt = """
        Analyze the attached Walmart receipt PDF.
        Extract ONLY the summary financial details: the Subtotal, the Tax, the Driver Tip, and the final Total amount.
        Do not extract any individual line items.
        """

        summary_response = summary_model.generate_content(
            [summary_prompt, uploaded_file]
        )
        summary_result_object = summary_response.candidates[0].content.parts[0].text
        summary_data = Summary.model_validate_json(summary_result_object)
        summary_dict = summary_data.model_dump()

        # --- COMBINE RESULTS ---
        print("Successfully parsed both items and summary.")
        receipt_dict = {"items": items_list, "summary": summary_dict}

        return receipt_dict

    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    receipt_path = pathlib.Path("test-1.pdf")
    if receipt_path.exists():
        parsed_receipt = parse_walmart_pdf(receipt_path)
        if parsed_receipt:
            print(json.dumps(parsed_receipt, indent=2))
        else:
            print("Failed to parse the receipt.")
    else:
        print(f"File does not exist: {receipt_path}")
