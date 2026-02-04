import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
  Image,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';

interface Post {
  id: string;
  competitorId: string;
  competitorName: string;
  competitorAvatar?: string;
  content: string;
  imageUrl?: string;
  platform: 'vk' | 'telegram' | 'instagram';
  likes: number;
  views: number;
  createdAt: Date;
}

type NavigationProp = NativeStackNavigationProp<RootStackParamList, 'Feed'>;

export const FeedScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const [posts, setPosts] = useState<Post[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadPosts();
  }, []);

  const loadPosts = async () => {
    // TODO: Загрузка постов из API
    const mockPosts: Post[] = [
      {
        id: '1',
        competitorId: '1',
        competitorName: 'Конкурент А',
        content: 'Запустили новую рекламную кампанию! 🚀',
        platform: 'vk',
        likes: 245,
        views: 1520,
        createdAt: new Date(),
      },
      {
        id: '2',
        competitorId: '2',
        competitorName: 'Конкурент Б',
        content: 'Скидки до 50% на весь ассортимент!',
        imageUrl: 'https://via.placeholder.com/400x200',
        platform: 'telegram',
        likes: 189,
        views: 980,
        createdAt: new Date(Date.now() - 3600000),
      },
    ];
    setPosts(mockPosts);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadPosts();
    setRefreshing(false);
  };

  const getPlatformColor = (platform: string) => {
    switch (platform) {
      case 'vk':
        return '#0077FF';
      case 'telegram':
        return '#0088CC';
      case 'instagram':
        return '#E4405F';
      default:
        return '#666';
    }
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 60) return 'только что';
    if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;
    return `${Math.floor(diff / 86400)} д назад`;
  };

  const renderPost = ({ item }: { item: Post }) => (
    <TouchableOpacity
      style={styles.postCard}
      onPress={() => navigation.navigate('PostDetail', { postId: item.id })}
    >
      <View style={styles.postHeader}>
        <View style={styles.competitorInfo}>
          {item.competitorAvatar ? (
            <Image
              source={{ uri: item.competitorAvatar }}
              style={styles.avatar}
            />
          ) : (
            <View style={[styles.avatar, styles.avatarPlaceholder]}>
              <Text style={styles.avatarText}>
                {item.competitorName.charAt(0)}
              </Text>
            </View>
          )}
          <View style={styles.headerText}>
            <Text style={styles.competitorName}>{item.competitorName}</Text>
            <View style={styles.metaInfo}>
              <View
                style={[
                  styles.platformBadge,
                  { backgroundColor: getPlatformColor(item.platform) },
                ]}
              >
                <Text style={styles.platformText}>
                  {item.platform.toUpperCase()}
                </Text>
              </View>
              <Text style={styles.timeText}>{formatTime(item.createdAt)}</Text>
            </View>
          </View>
        </View>
      </View>

      <Text style={styles.content}>{item.content}</Text>

      {item.imageUrl && (
        <Image source={{ uri: item.imageUrl }} style={styles.postImage} />
      )}

      <View style={styles.postFooter}>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>❤️ {item.likes}</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statLabel}>👁 {item.views}</Text>
        </View>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={posts}
        renderItem={renderPost}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Нет постов</Text>
            <Text style={styles.emptySubtext}>
              Добавьте конкурентов для отслеживания
            </Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  listContent: {
    padding: 16,
  },
  postCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  postHeader: {
    marginBottom: 12,
  },
  competitorInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    marginRight: 12,
  },
  avatarPlaceholder: {
    backgroundColor: '#E0E0E0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#666',
  },
  headerText: {
    flex: 1,
  },
  competitorName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  metaInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  platformBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginRight: 8,
  },
  platformText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  timeText: {
    fontSize: 12,
    color: '#999',
  },
  content: {
    fontSize: 15,
    lineHeight: 22,
    color: '#333',
    marginBottom: 12,
  },
  postImage: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginBottom: 12,
  },
  postFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F0F0F0',
  },
  stat: {
    marginRight: 20,
  },
  statLabel: {
    fontSize: 14,
    color: '#666',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#999',
  },
});
