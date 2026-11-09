// SON.Desktop/Views/ChatView.xaml.cs
using System.Collections.Specialized;
using System.Windows.Controls;
using System.Windows.Input;
using SON.Desktop.ViewModels;

namespace SON.Desktop.Views
{
    public partial class ChatView : UserControl
    {
        public ChatView()
        {
            InitializeComponent();
            DataContextChanged += OnDataContextChanged;
        }

        private void OnDataContextChanged(object sender, System.Windows.DependencyPropertyChangedEventArgs e)
        {
            if (e.NewValue is ChatViewModel vm)
            {
                vm.Messages.CollectionChanged += OnMessagesChanged;
            }
        }

        private void OnMessagesChanged(object? sender, NotifyCollectionChangedEventArgs e)
        {
            if (e.Action == NotifyCollectionChangedAction.Add)
            {
                Dispatcher.InvokeAsync(() =>
                {
                    MessagesScrollViewer.ScrollToEnd();
                });
            }
        }

        private void InputBox_PreviewKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter && !Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
            {
                e.Handled = true;
                if (DataContext is ChatViewModel vm && vm.SendMessageCommand.CanExecute(null))
                {
                    vm.SendMessageCommand.Execute(null);
                }
            }
        }
    }
}

