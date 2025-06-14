import os
from database import AntDatabase
from dotenv import load_dotenv

def load_species_from_file(filename):
    # Load environment variables
    load_dotenv()
    
    # Get database credentials from environment variables
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', '')
    db_name = os.getenv('DB_NAME', 'antmaster')
    
    # Initialize database connection
    db = AntDatabase(db_host, db_user, db_password, db_name)
    
    # Read species from file
    with open(filename, 'r', encoding='utf-8') as f:
        species_list = [line.strip() for line in f if line.strip() and not line.startswith('/')]
    
    # Add each species to the database
    success_count = 0
    error_count = 0
    
    for species in species_list:
        try:
            if db.add_species(species):
                success_count += 1
                print(f"Added species: {species}")
            else:
                error_count += 1
                print(f"Failed to add species: {species}")
        except Exception as e:
            error_count += 1
            print(f"Error adding species {species}: {str(e)}")
    
    print(f"\nSummary:")
    print(f"Successfully added: {success_count} species")
    print(f"Failed to add: {error_count} species")

if __name__ == "__main__":
    load_species_from_file("especies_hormigas.txt") 