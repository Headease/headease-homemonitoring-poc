terraform {
  backend "gcs" {
    bucket = "cumuluz-vws-hackathon-april-26-tf-state"
    prefix = "terraform/state"
  }
}
