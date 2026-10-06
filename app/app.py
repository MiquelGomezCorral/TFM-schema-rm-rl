"""Local Dash entry point for the Reward Machine web interface."""

import dotenv

from scripts import generate_rm
from src.web import RunController, create_app

dotenv.load_dotenv()
app = create_app(RunController(generate_rm))


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
