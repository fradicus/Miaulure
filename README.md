# Miaulure
# Cat Activity Heatmap

## Overview
The Cat Activity Heatmap project visualizes cat activity logs by generating heatmaps based on the positions of the cat over time. The application retrieves data from a MongoDB database and uses matplotlib for visualization. This project is useful for cat owners and researchers interested in understanding cat behavior patterns.

## Project Structure
```
cat-activity-heatmap
├── src
│   ├── hyperion.py        # Main entry point for the application
│   └── dailyheat.py       # Logic for generating heatmaps from activity logs
├── requirements.txt        # Python dependencies for the project
└── README.md               # Documentation for the project
```

## Setup Instructions
1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/cat-activity-heatmap.git
   cd cat-activity-heatmap
   ```

2. **Install Dependencies**
   It is recommended to use a virtual environment. You can create one using `venv` or `conda`.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

## Usage
1. **Configure MongoDB Connection**
   Update the MongoDB connection string in `src/dailyheat.py` with your own credentials.

2. **Run the Application**
   Execute the main script to generate the heatmap.
   ```bash
   python src/hyperion.py
   ```

3. **Input Date Range**
   Modify the date range in `src/dailyheat.py` to specify the time period for which you want to generate the heatmap.

## Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.
