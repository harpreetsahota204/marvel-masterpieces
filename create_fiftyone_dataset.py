import fiftyone as fo
from pathlib import Path
import pandas as pd

def create_marvel_dataset():
    """
    Creates a FiftyOne dataset from Marvel Masterpieces trading cards.
    Each piece of information is stored as a separate Label.

    Returns:
        fo.Dataset: FiftyOne dataset containing the trading card images and labels
    """
    # Initialize dataset
    dataset = fo.Dataset("marvel_masterpieces", overwrite=True, persistent=True)

    # Read CSV metadata
    csv_path = Path('./download_images/marvel_masterpieces_images/character_info.csv')
    metadata_df = pd.read_csv(csv_path)

    # Base directory for images
    image_dir = Path('marvel_masterpieces_images')

    # Create list to store all samples
    samples = []

    # Create samples for each image
    for _, row in metadata_df.iterrows():
        # Construct image path
        image_path = image_dir / row['Filename']

        # Create FiftyOne sample
        sample = fo.Sample(filepath=str(image_path))

        # Add information as separate Labels
        sample["pseudonym"] = fo.Classification(label=str(row['Pseudonym']))
        sample["character"] = fo.Classification(label=row['Character Name'])
        sample["universe"] = fo.Classification(label=row['Universe'])
        sample["year"] = fo.Classification(label=str(row['Year']))

        samples.append(sample)

    # Add all samples at once
    dataset.add_samples(samples)

    return dataset

if __name__ == "__main__":
    # Create and load the dataset
    dataset = create_marvel_dataset()

    # Print dataset statistics
    print("\nDataset Statistics:")
    print(f"Number of samples: {len(dataset)}")
    print("\nUnique characters:", dataset.distinct("character.label"))
    print("\nUnique universes:", dataset.distinct("universe.label"))
    print("\nUnique years:", dataset.distinct("year.label"))
