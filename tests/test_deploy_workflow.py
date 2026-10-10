from pathlib import Path
import unittest


class StagingDeploymentWorkflowTests(unittest.TestCase):
    def test_waits_for_the_new_lightsail_deployment_version(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "deploy-staging.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("containerService.nextDeployment.version", workflow)
        self.assertIn("steps.deployment.outputs.version", workflow)
        self.assertIn("get-container-service-deployments", workflow)
        self.assertIn("currentDeployment.version,url", workflow)

    def test_published_image_tag_is_unique_for_every_workflow_attempt(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "deploy-staging.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "IMAGE_TAG: ${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
            workflow,
        )
        self.assertNotIn("IMAGE_TAG: ${{ github.sha }}\n", workflow)


if __name__ == "__main__":
    unittest.main()
