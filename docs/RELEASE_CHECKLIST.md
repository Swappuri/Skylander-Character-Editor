# First GitHub release checklist

1. Create a new empty GitHub repository.
2. Upload/push the contents of this folder to the repository root.
3. Check that Actions are enabled and that the `Build and publish release assets` workflow passes.
4. Create and push a version tag, for example:

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

5. Wait for the workflow to build all four platform packages and attach them to the GitHub Release.
6. Test each release package on its target OS before announcing it publicly.

Do not label the release as fully compatible with all six games until cross-generation figure tests and in-game validation have been completed.
