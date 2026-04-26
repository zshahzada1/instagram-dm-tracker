"""Comments fetcher for Instagram media.

Opens a real browser, navigates to the reel/post, clicks the comment button,
and intercepts the PolarisPostCommentsContainerQuery response to extract comments.

Read-only: Never clicks Like or Reply buttons.
"""

from .fetcher import fetch_comments, CommentsResult, Comment, CommentUser, CommentsNotLoadedError, CommentFetchError

__all__ = [
    'fetch_comments',
    'CommentsResult',
    'Comment',
    'CommentUser',
    'CommentsNotLoadedError',
    'CommentFetchError',
]
