# Eyball anomaly detection engine

Implement a class to detect image anomalies using an AI model, which can be called from visual checking automation.

![Eyball](eyball3.png "Eyball")

Date: 5/28/2024

Fulmine Labs LLC

## Overview

This Python code implements a class wrapper around an Anomaly Detection model which can be used to visually check if an image or screenshot is anomalous or not. 

The supported architecture for this model is 'Siamese Network'. In order to reduce false negatives the code compares the image against a jury of randomly selected known good images of configurable size 'jury_size'.  If the number of jurors who vote that the image is simlar to the chosen known good image is below a configurable 'threshold' then the code returns a verdict of 'Anomalous', otherwise it returns a verdict of 'Normal'. If an image path is not specified but screen coordinates are, these will be used instead, enabling direct integration with automated visual checking scripts.

One goal is to use this class as part of automating visual checking of a medical image (PACS) production pipeline, although it could theoretically visually check any type of image on which the model has been trained.

For comparison purposes, Eyball also has the capability of describing the images or screenshot, using GPT-4 Turbo Vision, when an OpenAI API key is supplied in the 'Eyball-OpenAI_key.txt' file.

## Datasources used

Cancer Imaging Archive images, stored in Orthanc.

CT Lung images randomly selected from internet sources for testing

## Current Version
The current stable version of the project is 0.1
See the [CHANGELOG.md](CHANGELOG.md) file for details about this version.

## Prerequisites

* Anaconda, with an environment having the Python libraries listed in [requirements.txt](requirements.txt)
* A Siamese Network model, trained on similar 'normal' images and anomalous images. For demonstration purposes, the model stored in the Fulmine LABS mini PACS repository can be used.
* An Open AI account, with API access to the latest models (gpt-4-turbo at the time of writing).
* A folder containing known good images. For demonstration purposes, these images were studies obtained from the Cancer Imaging Archive database, stored in Orthanc.

## Usage

* Install Anaconda, create an environment and install the dependencies in requirements.txt
* Obtain all Files and folders from this repository from github
* Open Eyball.ipynb In a Jupyter lab session
* Create a folder (optionally, with subfolders) of at least _jury_size_) known good PNG images, against which the target image can be compared to detect an anomaly and modify the variable _known_good_images_folder_ in cell 19 accordingly
* Copy the Fulmine LABS mini-PACS generated Siamese Network model to a local models folder and modify the variable _siamese_model_path_ accordingly
* Create and fund an OpenAI account and store the key in the local 'Eyball-OpenAI_key.txt' file. Note that running this script will access the OpenAI API about 100 times, with corresponding charges (total of a few cents at the time of writing). Note: gpt-4-o is cheaper/faster and initial tests suggest similar performance.
* Update the local file _Eyball-OpenAI_key.txt_ to contain the API key and modify variable _api_key_file_ accordingly
* Other variables in cell 19 can be modified, if needed
* Execute the script within Jupyter Lab.
* The script will start by assessing some sample images from the repository. These include a) normal images from the same set of Lung CT studies that were used for training, b) images that are obviously not medical images, c) images that are Lung CT medical images selected from the internet and d) images that are Lung CT medical images but with some subtle, unwanted post-processing artefacts. A screenshot of a portion whatever is on the screen at the time of execution e) is also captured and used. In each case both models are called.
* The script then interates over 40 (_sample_size_) normal and anomalous images to produce an F1 score for model comparison.

## Testing

Observations regarding the sample images:

* The internet image: _custom_test_valid\low-dose-lung-cancer-screening-with-lung-nodules.jpg_ was correctly assessed as Normal by ChatGPT model but was incorrectly assessed as Anomalous by the Siamese Network model, perhaps due to none of the training images having similar nodules. This speaks well to the ablity of the ChatGPT model to generalize.
* If the image is clearly anomalous the ChatGPT model just returns 'Anomalous', which is desirable behavior as we are being charged for bandwidth over the API. However, a nice feature of the ChatGPT model is that it can be instructed to also return a description of the Anomaly for more subtle cases for example: _LLM description The image is a typical medical image (CT scan) but includes an arrow overlay pointing to a specific area_ or _LLM prediction The image is a typical medical image (e.g., a CT scan) but has a clear textual overlay stating "System Error Please restart." This indicates the presence of an error message that was likely added by the PACS image viewer technology_. This could help with quickly isolating issues.
* Two images with a text overlay, which should have been classed as anomalous based on the prompt passed to ChatGPT _custom_invalid\Lung_abscess_-_CT_with_overlay.jpg_ and _Custom_invalid\internet-gettyimages-1320918955-612x612_small_label.jpg_, were classed as Normal. The Siamese Network which was entirely trained without overlays correctly classed these as Anomalous.

F1 scores:

Using a sample of the provided images and the Fulmine LAB mini PACS Siamese Network custom model:
Evaluation Results - Siamese Model: {'accuracy': 0.975, 'precision': 0.975, 'recall': 0.975, 'f1': 0.975}

Compared with gpt-4-turbo:
Evaluation Results - GPT Model: {'accuracy': 0.875, 'precision': 0.9166666666666666, 'recall': 0.825, 'f1': 0.868421052631579}

Generally, the GPT model struggles a bit with unusual image aquisition features such as parts of the scanner that were included in the image and tends to classify these as anomalous. Conversely, artefacts which could be post processing artefacts were classed more often as Normal by the GPT model. 
For reference, this was the prompt:

_If the image is obviously not a medical image, state *** ANOMALOUS ***._

_If it is a typical medical image as acquired by an imaging modality with no additions or enhancements, state *** NORMAL ***._

_Otherwise, if it is a medical image but it also clearly has textual overlays or annotations or digital or image processing artifacts that could have been added by the PACS image viewer technology, describe those features and append *** ANOMALOUS ***._

Empirically, the order of these clauses within the prompt can make a significant difference to the outcome, so perhaps additional prompt engineering would help.

Conclusion: While the OpenAI model is currently not as performant as the custom model and there is a small cost, it takes no additional effort to train and it is expected that future LLM models will have improved performance. 

The next step is to use Eyball in real-world tests, by running it against the OHIF viewer.

## Known issues

* Some cleanup of the logging is required
* Error handling is currently rudimentary
* The OpenAI model name should also be a variable

## Acknowledgements

This code was written collaboratively with [GPT-4V](https://chat.openai.com/). Thank you Assistant!
The Cancer Imaging Archive
Orthanc

## License
MIT open source license

## Collaboration
We welcome contributions at all levels of experience, whether it's with code, documentation, tests, bug reports, feature requests, or other forms of feedback. If you're interested in helping improve this tool, here are some ways you can contribute:

Ideas for Improvements: Have an idea that could make the Fulmine Labs mini-PACS better? Open an issue with the tag enhancement to start a discussion about your idea.

Bug Reports: Notice something amiss? Submit a bug report under issues, and be sure to include as much detail as possible to help us understand the problem.

Feature Requests: If you have a suggestion for a new feature, describe it in an issue with the tag feature request.

Documentation: Good documentation is just as important as good code. Although this is currently a very simple tool, if you'd like to contribute documentation, we'd greatly appreciate it.

Code: If you're looking to update or write new code, check out the open issues and look for ones tagged with good first issue or help wanted.

## Contact
Duncan Henderson, Fulmine Labs LLC henderson.duncanj@gmail.com
