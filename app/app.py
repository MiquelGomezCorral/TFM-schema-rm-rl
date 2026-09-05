"""Local Dash entry point for the Reward Machine web interface."""

import dotenv

from src.web import create_app


dotenv.load_dotenv()
app = create_app()


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
