import os
import shutil
import fiftyone as fo
from dataclasses import dataclass
from typing import List, Dict

from fiftyone.utils.huggingface import load_from_hub

dataset = load_from_hub(
    "harpreetsahota/marvel-masterpieces",
    name="marvel-masterpieces",
    overwrite=True
    )

@dataclass
class FileLocations:
    """
    Manages file paths for processing 3D meshes and masks.

    Attributes:
        output_dir (str): Directory where all output files will be saved
        subdirectory (str): Temporary subdirectory for initial file creation, defaults to "0"

    Example:
        >>> locations = FileLocations("meshes_masks")
        >>> paths = locations.get_paths("sample_123")
        >>> print(paths['target_mask'])
        'meshes_masks/sample_123.png'
    """
    output_dir: str
    subdirectory: str = "0"

    def get_paths(self, sample_id: str) -> Dict[str, str]:
        """
        Generate all necessary file paths for a given sample.

        Args:
            sample_id (str): Unique identifier for the sample

        Returns:
            dict: Dictionary containing paths for:
                - original_mask: Initial mask file location
                - target_mask: Final mask file location
                - original_mesh: Initial mesh file location
                - target_mesh: Final mesh file location
                - scene_path: Path for the 3D scene file

        Example:
            >>> locations = FileLocations("meshes_masks")
            >>> paths = locations.get_paths("sample_123")
            >>> paths['original_mask']
            'meshes_masks/0/input.png'
        """
        return {
            'original_mask': os.path.join(self.output_dir, self.subdirectory, "input.png"),
            'target_mask': os.path.join(self.output_dir, f"{sample_id}.png"),
            'original_mesh': os.path.join(self.output_dir, self.subdirectory, "mesh.glb"),
            'target_mesh': os.path.join(self.output_dir, f"{sample_id}.glb"),
            'scene_path': os.path.join(self.output_dir, f"{sample_id}.fo3d")
        }

def create_dataset(name: str) -> fo.Dataset:
    """
    Initialize a new FiftyOne dataset with group field support.

    Args:
        name (str): Name of the dataset to create

    Returns:
        fo.Dataset: Newly created dataset with group field initialized

    Example:
        >>> dataset = create_dataset("my_reconstructions")
        >>> print(dataset.name)
        'my_reconstructions'
    """
    dataset = fo.Dataset(name, persistent=True, overwrite=True)
    dataset.add_group_field("group", default="input")
    return dataset

def move_files(paths: Dict[str, str]) -> None:
    """
    Move generated files from temporary subdirectory to main output directory.

    Args:
        paths (dict): Dictionary containing original and target paths for mask and mesh files
                     Must include keys: 'original_mask', 'target_mask', 'original_mesh', 'target_mesh'

    Example:
        >>> paths = {
        ...     'original_mask': 'meshes_masks/0/input.png',
        ...     'target_mask': 'meshes_masks/sample_123.png',
        ...     'original_mesh': 'meshes_masks/0/mesh.glb',
        ...     'target_mesh': 'meshes_masks/sample_123.glb'
        ... }
        >>> move_files(paths)
    """
    shutil.move(paths['original_mask'], paths['target_mask'])
    shutil.move(paths['original_mesh'], paths['target_mesh'])

def create_sample(filepath: str, group_element: str, metadata: fo.Sample) -> fo.Sample:
    """
    Create a new FiftyOne sample with metadata copied from an existing sample.

    Args:
        filepath (str): Path to the file associated with this sample
        group_element (str): Group identifier for the sample
        metadata (fo.Sample): Original sample containing metadata to copy

    Returns:
        fo.Sample: New sample with copied metadata and specified filepath/group

    Example:
        >>> original_sample = fo.Sample(filepath="image.jpg", pseudonym="hero", character="protagonist")
        >>> new_sample = create_sample("mask.png", "mask_group", original_sample)
    """
    return fo.Sample(
        filepath=filepath,
        group=group_element,
        pseudonym=metadata.pseudonym,
        character=metadata.character,
        universe=metadata.universe,
        year=metadata.year
    )

def create_3d_scene(mesh_filename: str, scene_path: str, output_dir: str) -> None:
    """
    Create and save a 3D scene with a mesh and camera setup.

    Args:
        mesh_filename (str): Filename of the mesh to include in the scene
        scene_path (str): Path where the scene file will be saved
        output_dir (str): Directory where the scene will be created

    Example:
        >>> create_3d_scene("model.glb", "scene.fo3d", "output_directory")
    """
    scene = fo.Scene()
    scene.camera = fo.PerspectiveCamera(up="Y")

    mesh = fo.GltfMesh("mesh", mesh_filename)
    mesh.rotation = fo.Euler(0, 180, 0, degrees=True)
    scene.add(mesh)

    current_dir = os.getcwd()
    os.chdir(output_dir)
    scene.write(os.path.basename(scene_path))
    os.chdir(current_dir)

def cleanup_subdirectory(subdir: str) -> None:
    """
    Remove empty subdirectory if it exists.

    Args:
        subdir (str): Path to the subdirectory to clean up

    Example:
        >>> cleanup_subdirectory("meshes_masks/0")
    """
    if os.path.exists(subdir) and not os.listdir(subdir):
        os.rmdir(subdir)

def process_samples(dataset: fo.Dataset, output_dir: str) -> None:
    """
    Process a dataset of samples to create masks, meshes, and 3D scenes.

    This function performs the following steps for each sample:
    1. Runs external 3D reconstruction script
    2. Organizes output files
    3. Creates mask and mesh samples
    4. Generates 3D scenes
    5. Adds all samples to a new dataset

    Args:
        dataset (fo.Dataset): Input dataset containing samples to process
        output_dir (str): Directory where all output files will be saved

    Example:
        >>> input_dataset = fo.Dataset("input_data")
        >>> process_samples(input_dataset, "meshes_masks")
    """
    file_locations = FileLocations(output_dir)
    recon_dataset = create_dataset("reconstructions")

    for sample in dataset:
        # Run external script
        os.system(f"python /content/stable-fast-3d/run.py {sample.filepath} --output-dir {output_dir} --remesh_option quad")

        paths = file_locations.get_paths(sample.id)
        move_files(paths)

        # Create group and samples
        group = fo.Group()
        samples = []

        # Create and add samples
        samples.append(create_sample(sample.filepath, group.element("input"), sample))
        samples.append(create_sample(paths['target_mask'], group.element("mask"), sample))

        # Create 3D scene
        create_3d_scene(
            os.path.basename(paths['target_mesh']),
            paths['scene_path'],
            output_dir
        )

        samples.append(create_sample(paths['scene_path'], group.element("mesh"), sample))
        recon_dataset.add_samples(samples)

        # Cleanup
        cleanup_subdirectory(os.path.join(output_dir, file_locations.subdirectory))

    recon_dataset.compute_metadata()
    recon_dataset.save()

    return recon_dataset

# Usage
# output_dir = "meshes_masks"
# recon_dataset = process_samples(dataset, output_dir)