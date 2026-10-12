"""Local Dash entry point for the Reward Machine web interface."""

import dotenv
from maikol_utils.print_utils import print_color

from scripts import generate_rm
from src.config import Configuration
from src.web import RunController, create_app

dotenv.load_dotenv()
app = create_app(RunController(generate_rm))


if __name__ == "__main__":
    print_color("Embeddings need the local llama-server. Start it with:", "bold_yellow")
    print_color(Configuration().llama_server_command(), "yellow")
    app.run(debug=False, use_reloader=False)
