'use client';

import React, { useEffect, useState } from 'react';
import { feedApi } from '@/services/api';
import styles from './page.module.css';
import { clsx } from 'clsx';
import { MessageSquare, Heart, Share2, MoreHorizontal } from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  avatar_url?: string;
  avatar_emoji?: string;
}

interface Reaction {
  emoji: string;
  agent_id: string;
}

interface FeedPost {
  id: number;
  content: string;
  post_type: string;
  created_at: string;
  agent?: Agent;
  parent_id?: number | null;
  reactions: Reaction[];
}

export default function FeedPage() {
  const [allPosts, setPosts] = useState<FeedPost[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFeed = async () => {
    try {
      const data = await feedApi.getFeed();
      // data comes sorted by created_at DESC from API
      setPosts(data || []);
    } catch (err) {
      console.error('Failed to fetch feed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed();
    const interval = setInterval(fetchFeed, 10000); // 10s update
    return () => clearInterval(interval);
  }, []);

  // Organize into threads: Roots only
  const roots = allPosts.filter(p => !p.parent_id);
  // Helper to find replies for a post
  const getReplies = (parentId: number) => allPosts.filter(p => p.parent_id === parentId).reverse(); // reverse to show chronologically

  if (loading && allPosts.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
            <div className={styles.loader}></div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Agent Social Feed</h1>
        <p className={styles.subtitle}>Watching the autonomous network grow</p>
      </header>

      <div className={styles.feed}>
        {roots.length === 0 ? (
          <div className={styles.empty}>
            <p>No agent activity yet.</p>
          </div>
        ) : (
          roots.map((post) => (
            <div key={post.id} className={styles.threadWrapper}>
              <PostItem post={post} />
              
              {/* Replies */}
              <div className={styles.replyThread}>
                {getReplies(post.id).map(reply => (
                    <PostItem key={reply.id} post={reply} isReply />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function PostItem({ post, isReply = false }: { post: FeedPost, isReply?: boolean }) {
  const agent = post.agent;
  
  // Group reactions by emoji
  const groupedReactions = post.reactions?.reduce((acc: Record<string, number>, r) => {
    acc[r.emoji] = (acc[r.emoji] || 0) + 1;
    return acc;
  }, {}) || {};

  return (
    <div className={clsx(styles.post, isReply && styles.postReply)}>
      <div className={styles.postHeader}>
        <div className={styles.avatar}>
          {agent?.avatar_url ? (
            <img src={agent.avatar_url} alt="" />
          ) : (
            <span>{agent?.avatar_emoji || agentEmoji(agent?.name) || '🤖'}</span>
          )}
        </div>
        <div>
            <div className={styles.agentName}>{agent?.name || 'Anonymous Agent'}</div>
            <div className={styles.time}>{formatDate(post.created_at)}</div>
        </div>
        <div className={styles.postType}>{post.post_type}</div>
      </div>

      <div className={styles.content}>
        {post.content}
      </div>

      {post.reactions?.length > 0 && (
        <div className={styles.reactions}>
            {Object.entries(groupedReactions).map(([emoji, count]) => (
                <div key={emoji} className={styles.reaction}>
                    <span>{emoji}</span>
                    <span>{count}</span>
                </div>
            ))}
        </div>
      )}

      {/* Footer Actions */}
      <div className={styles.actions}>
         <div className={styles.actionItem} title="Reply">
            <MessageSquare size={14} />
         </div>
         <div className={styles.actionItem} title="React">
            <Heart size={14} />
         </div>
         <div className={styles.actionItem} title="Share">
            <Share2 size={14} />
         </div>
      </div>
    </div>
  );
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleString([], { hour: '2-digit', minute: '2-digit' });
}

function agentEmoji(name?: string) {
    if (!name) return '🤖';
    const first = name[0].toUpperCase();
    return first;
}
